"""Response envelopes reuse the canonical explanation schema without renaming it."""
from copy import deepcopy
from harpisense_contracts.schema_source import SCHEMAS


def obj(properties, required=None):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,
            'additionalProperties':False}


def nullable(spec):
    return {'anyOf':[spec,{'type':'null'}]}


TEXT={'type':'string'}
NUMBER={'type':'number'}
BOOLEAN={'type':'boolean'}
IDREF=obj({'id':TEXT,'revision':{'type':'integer','minimum':1}})
REASON=nullable(TEXT)
RISK=obj({
    'state':{'enum':['incident_not_selected','affine_transform','different_class_not_additively_mapped','nonlinear_transform_not_additively_mapped']},
    'risk_score_explained':{'const':False}, 'factor':{'enum':['detection','anomaly']}, 'formula':TEXT,
    'scenario_id':nullable(TEXT), 'source_probability':NUMBER, 'scale':nullable(NUMBER), 'offset':nullable(NUMBER),
    'rounding':obj({'mode':{'const':'ROUND_HALF_UP'},'decimal_places':{'const':6}}),
    'factor_value':NUMBER,'recorded_factor_value':nullable(NUMBER),'matches_recorded_factor':nullable(BOOLEAN),
    'score_direction':{'const':'higher_is_more_anomalous'},'anomaly_threshold':NUMBER,'anomaly_margin':NUMBER,
    'is_anomaly':BOOLEAN,'normal_reference_percentile':NUMBER,'limitation':TEXT,
},['state','risk_score_explained'])

RECORD=deepcopy(SCHEMAS['explanation'])
RECORD.pop('$id',None)
PROPERTIES=SCHEMAS['detection']['properties']
ITEM=obj({'id':TEXT,'projection_revision':{'type':'integer','minimum':1},
    'in_incident_explanation_refs':nullable(BOOLEAN),
    'record':{'$ref':'#/components/schemas/XAIExplanationRecord'},
    'output_direction':{'enum':['positive_increases_class_probability','positive_increases_anomaly_score']},
    'coherence':obj({'reconstructed_output':NUMBER,'absolute_error':NUMBER,
        'reconstruction_tolerance':{'const':1e-8},'detection_output_tolerance':{'const':1e-6},
        'residual_tolerance':{'const':1e-5},'causality_or_detector_accuracy_proven':{'const':False}}),
    'risk_mapping':RISK})
ANALYSIS=obj({'detection_id':TEXT,'state':{'enum':['available','absent','invalid','unavailable']},
    'reason_code':REASON,'explanations':{'type':'array','items':ITEM},
    'rejected_explanations':{'type':'array','items':obj({'id':TEXT,'reason_code':{'const':'INVALID_RECORD_OR_LINK'}})},
    'has_more':BOOLEAN,'detection_revision':{'type':'integer','minimum':1},
    'model':PROPERTIES['model'],'window':PROPERTIES['window'],'entity':PROPERTIES['entity'],
    'input_fingerprint':PROPERTIES['input_fingerprint'],
    'observation_ref':obj({'window_id':TEXT,'collection_session_id':TEXT,'sensor_id':TEXT}),
    'asset':obj({'technical_id':nullable(TEXT),'display_name':nullable(TEXT),
                 'name_state':{'enum':['available','unregistered','not_identified']},
                 'name_source':{'enum':['asset_registry','asset_projection',None]}}),
    'incident_ref':nullable(IDREF),
    'operational_outputs':obj({'classification':PROPERTIES['classification'],'anomaly':PROPERTIES['anomaly']}),
},['detection_id','state','reason_code','explanations','rejected_explanations','has_more'])
ANALYSES={'type':'array','items':{'$ref':'#/components/schemas/XAIAnalysis'}}
MODELS={'XAIExplanationRecord':RECORD,'XAIAnalysis':ANALYSIS,
        'XAIIncident':obj({'incident_ref':IDREF,'state':{'enum':['available','absent_or_unavailable']},
                          'analyses':ANALYSES,'read_only':{'const':True}}),
        'XAIObservation':obj({'observation_ref':obj({'collection_session_id':TEXT,'window_id':TEXT,'sensor_id':nullable(TEXT)}),
                            'analyses':ANALYSES,'has_more':BOOLEAN,'read_only':{'const':True}})}
