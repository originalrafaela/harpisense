from harpisense_contracts import input_fingerprint
from harpisense_catalog import CATALOG,ACTION_SPECS
NOW='2026-10-15T15:00:12Z'
def context(case='C01'):
    ds=[]
    for model in ['random_forest','isolation_forest']:
        ds.append(dict(schema_version='1.0.0',record_type='detection',detection_id=model+'-'+case,created_at='2026-10-15T15:00:11Z',
            window=dict(window_id='w1',collection_session_id='synthetic-test',sensor_id='edge-test',feature_schema_version='harpisense.if.window.v1',traffic_profile='test',start='2026-10-15T15:00:00Z',end='2026-10-15T15:00:10Z'),
            entity=dict(source_ip='192.0.2.10',destination_ip='192.0.2.20',device_id='poste-test',mqtt_client_id='mqtt-test'),
            model=dict(detector=model,model_version=model+'-test',input_dtype='float32'),quality=dict(status='VALID',valid_until='2026-10-15T15:01:10Z'),
            features={'packet_count':100.0},input_fingerprint=input_fingerprint({'packet_count':100.0}),
            classification=dict(predicted_class=case,accepted_class=case,probabilities={'normal':.02,case:.98},confidence=.98,attack_probability=.98,confidence_threshold=.7,needs_review=False) if model=='random_forest' else None,
            anomaly=dict(anomaly_score=.7,anomaly_threshold=.6,anomaly_margin=.1,is_anomaly=True,normal_reference_percentile=.99) if model=='isolation_forest' else None,
            block_authorized=False,provenance=dict(source_schema='synthetic-test',source_id=model)))
    kind=ACTION_SPECS[CATALOG[case]['actions'][0]][0]
    target=dict(target_ref='target-test',target_kind=kind,scope_ref='scope-test',verified=True,scope_allowed=True,protected=False,executor_ready=True,
        detection_refs=[d['detection_id'] for d in ds],allowed_parameters=dict(rate_profile_ref=['rate-test'],topic_ref=['topic-test'],permission=['SUBSCRIBE' if case=='C02' else 'PUBLISH'],message_id=['message-test']))
    events=[dict(evidence_id='e1',source_ref='trusted-collector',kind=CATALOG[case]['evidence_kind'],scenario_id=case,target_ref='target-test',scope_ref='scope-test',
        window_id='w1',collection_session_id='synthetic-test',observed_at='2026-10-15T15:00:10Z',verified=True,trigger_met=True,artifact_ref='synthetic://event-1')]
    return dict(scenario_id=case,detections=ds,explanations=[],evidence=events,target=target,
        asset=dict(asset_ref='poste-test',criticality=80,scope_ref='scope-test',inventory_version='test-v1'),trusted_sources={'trusted-collector':[CATALOG[case]['evidence_kind']]})
