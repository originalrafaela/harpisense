"""Exact persisted links, canonical validation and explicit numerical boundaries.

This reader imports no estimator, joblib, BitNet, dispatcher or XAI generator.
"""
import math
from decimal import Decimal, ROUND_HALF_UP

from psycopg.rows import dict_row
from psycopg import sql
from harpisense_contracts import validate, validate_links

OUTPUT_TOLERANCE = 1e-6
RESIDUAL_TOLERANCE = 1e-5
RECONSTRUCTION_TOLERANCE = 1e-8


class Missing(ValueError):
    pass


class XAIStore:
    def __init__(self, connect, installation_id=None, asset_identifier_column='technical_id'):
        if asset_identifier_column not in ('technical_id', 'device_id'):
            raise ValueError('Unsupported asset registry identifier')
        self.connect, self.installation_id = connect, installation_id
        self.asset_identifier_column = asset_identifier_column

    @staticmethod
    def rows(cur, kind, identifier):
        cur.execute('SELECT id,revision,source,data FROM projections WHERE kind=%s AND id=%s ORDER BY revision',
                    (kind, identifier))
        return cur.fetchall()

    def asset(self, cur, detection):
        technical = detection['entity']['device_id']
        result = {'technical_id': technical, 'display_name': None, 'name_state': 'unregistered' if technical else 'not_identified', 'name_source': None}
        if technical and self.installation_id:
            cur.execute("SELECT to_regclass('hs_config.asset') AS relation")
            if cur.fetchone()['relation']:
                cur.execute(sql.SQL('SELECT document FROM hs_config.asset WHERE installation_id=%s AND {}=%s').format(
                            sql.Identifier(self.asset_identifier_column)),
                            (self.installation_id, technical))
                row = cur.fetchone()
                if row:
                    name_key = 'name' if self.asset_identifier_column == 'device_id' else 'display_name'
                    name = row['document'].get(name_key)
                    if isinstance(name, str) and name.strip():
                        result.update(display_name=name, name_state='available', name_source='asset_registry')
        if technical and result['display_name'] is None:
            rows = self.rows(cur, 'asset', technical)
            document = rows[-1]['data'] if rows else {}
            name = document.get('display_name')
            if document.get('device_id', technical)==technical and isinstance(name,str) and name.strip():
                result.update(display_name=name,name_state='available',name_source='asset_projection')
        return result

    @staticmethod
    def risk_mapping(detection, explanation, incident):
        if incident is None:
            return {'state': 'incident_not_selected', 'risk_score_explained': False}
        rf = detection['classification']
        if rf:
            case = incident['scenario_id']
            label = explanation['target']['class_label']
            formula = '100 * P(scenario_id)' if case else '100 * (1 - P(normal))'
            source = rf['probabilities'].get(case, 0) if case else rf['attack_probability']
            scale = 100 if case and case == label else (-100 if not case and label == 'normal' else None)
            offset = 100 if scale == -100 else (0 if scale == 100 else None)
            factor = float(Decimal(str(100*source)).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP))
            recorded = incident['risk']['factors']['detection']
            return {'state': 'affine_transform' if scale is not None else 'different_class_not_additively_mapped',
                    'factor': 'detection', 'formula': formula, 'scenario_id': case,
                    'source_probability': source, 'scale': scale, 'offset': offset,
                    'rounding': {'mode': 'ROUND_HALF_UP', 'decimal_places': 6},
                    'factor_value': factor, 'recorded_factor_value': recorded,
                    'matches_recorded_factor': None if recorded is None else abs(factor-recorded)<1e-6,
                    'risk_score_explained': False}
        anomaly = detection['anomaly']
        factor = 100*anomaly['normal_reference_percentile'] if anomaly['is_anomaly'] else 0
        factor = float(Decimal(str(factor)).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP))
        recorded = incident['risk']['factors']['anomaly']
        return {'state': 'nonlinear_transform_not_additively_mapped', 'factor': 'anomaly',
                'formula': '100 * normal_reference_percentile if is_anomaly else 0',
                'score_direction': 'higher_is_more_anomalous',
                'anomaly_threshold': anomaly['anomaly_threshold'], 'anomaly_margin': anomaly['anomaly_margin'],
                'is_anomaly': anomaly['is_anomaly'], 'normal_reference_percentile': anomaly['normal_reference_percentile'],
                'factor_value': factor, 'recorded_factor_value': recorded,
                'matches_recorded_factor': None if recorded is None else abs(factor-recorded)<1e-6,
                'limitation': 'Contributions explain -score_samples only, not the gated empirical percentile or total Risk.',
                'risk_score_explained': False}

    def detection_view(self, cur, identifier, incident=None):
        rows = self.rows(cur, 'detection', identifier)
        base = {'detection_id': identifier, 'state': 'unavailable', 'reason_code': None,
                'explanations': [], 'rejected_explanations': [], 'has_more': False}
        if len(rows) != 1:
            base['reason_code'] = 'DETECTION_NOT_FOUND' if not rows else 'DETECTION_REVISION_AMBIGUOUS'
            return base
        detection = rows[0]['data']
        try:
            validate(detection)
            if detection['record_type'] != 'detection' or detection['detection_id'] != identifier:
                raise ValueError('Identity mismatch')
        except (ValueError, TypeError, KeyError):
            base['reason_code'] = 'INVALID_DETECTION_RECORD'
            return base
        base.update(detection_revision=rows[0]['revision'], model=detection['model'],
                    window=detection['window'], observation_ref={
                        'window_id': detection['window']['window_id'],
                        'collection_session_id': detection['window']['collection_session_id'],
                        'sensor_id': detection['window']['sensor_id']},
                    entity=detection['entity'], asset=self.asset(cur, detection),
                    input_fingerprint=detection['input_fingerprint'],
                    incident_ref=None if incident is None else {'id':incident['incident_id'],'revision':incident['revision']},
                    operational_outputs={'classification':detection['classification'], 'anomaly':detection['anomaly']})
        cur.execute("SELECT id,revision,data FROM projections WHERE kind='xai' AND data->>'detection_id'=%s "
                    'ORDER BY id,revision LIMIT 101', (identifier,))
        explanations = cur.fetchall()
        base['has_more'] = len(explanations)>100
        for row in explanations[:100]:
            explanation = row['data']
            try:
                if sum(r['id']==row['id'] for r in explanations)>1:
                    raise ValueError('Unpinned explanation revision')
                if row['id'] != explanation['explanation_id']:
                    raise ValueError('Identity mismatch')
                validate_links(detections=[detection], explanations=[explanation], incidents=[], decisions=[])
                contributions = explanation['contributions']
                reconstructed = explanation['base_value'] + math.fsum(c['contribution'] for c in contributions) + explanation['additivity_residual']
                error = abs(reconstructed-explanation['output_value'])
                if error>RECONSTRUCTION_TOLERANCE:
                    raise ValueError('Numerical reconstruction failed')
                base['explanations'].append({'id':row['id'], 'projection_revision':row['revision'],
                    'in_incident_explanation_refs':None if incident is None else row['id'] in incident['explanation_refs'],
                    'record':explanation, 'output_direction': 'positive_increases_class_probability' if detection['classification'] else 'positive_increases_anomaly_score',
                    'coherence':{'reconstructed_output':reconstructed,'absolute_error':error,
                        'reconstruction_tolerance':RECONSTRUCTION_TOLERANCE,
                        'detection_output_tolerance':OUTPUT_TOLERANCE,'residual_tolerance':RESIDUAL_TOLERANCE,
                        'causality_or_detector_accuracy_proven':False},
                    'risk_mapping':self.risk_mapping(detection, explanation, incident)})
            except (ValueError, TypeError, KeyError, OverflowError):
                base['rejected_explanations'].append({'id':row['id'],'reason_code':'INVALID_RECORD_OR_LINK'})
        base['state'] = 'available' if base['explanations'] else ('invalid' if explanations else 'absent')
        base['reason_code'] = None if base['explanations'] else ('INVALID_RECORD_OR_LINK' if explanations else 'EXPLANATION_NOT_PERSISTED')
        return base

    def detection(self, identifier, *, incident_id=None, incident_revision=None):
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            incident = self.select_incident(cur, incident_id, incident_revision) if incident_id else None
            if incident and identifier not in incident['detection_refs']:
                raise Missing('DETECTION_NOT_IN_INCIDENT')
            result = self.detection_view(cur, identifier, incident)
            if result['reason_code']=='DETECTION_NOT_FOUND':
                raise Missing('DETECTION_NOT_FOUND')
            return result

    def select_incident(self, cur, identifier, revision):
        rows = self.rows(cur, 'incident', identifier)
        selected = [r for r in rows if revision is None or r['revision']==revision]
        if not selected:
            raise Missing('INCIDENT_NOT_FOUND')
        row = selected[-1]
        incident = row['data']
        validate(incident)
        if incident['record_type']!='incident' or incident['incident_id']!=identifier or incident['revision']!=row['revision']:
            raise ValueError('INVALID_INCIDENT_RECORD')
        return incident

    def incident(self, identifier, revision=None):
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            incident = self.select_incident(cur, identifier, revision)
            items = [self.detection_view(cur, ref, incident) for ref in incident['detection_refs']]
            return {'incident_ref':{'id':identifier,'revision':incident['revision']},
                    'state':'available' if any(i['state']=='available' for i in items) else 'absent_or_unavailable',
                    'analyses':items, 'read_only':True}

    def observation(self, session_id, window_id, sensor_id=None):
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cur.execute("SELECT DISTINCT id FROM projections WHERE kind='detection' "
                        "AND data->'window'->>'collection_session_id'=%s AND data->'window'->>'window_id'=%s "
                        "AND (%s::text IS NULL OR data->'window'->>'sensor_id'=%s) ORDER BY id LIMIT 201",
                        (session_id, window_id, sensor_id, sensor_id))
            rows = cur.fetchall()
            return {'observation_ref':{'collection_session_id':session_id,'window_id':window_id,'sensor_id':sensor_id},
                    'analyses':[self.detection_view(cur,row['id']) for row in rows[:200]],
                    'has_more':len(rows)>200, 'read_only':True}
