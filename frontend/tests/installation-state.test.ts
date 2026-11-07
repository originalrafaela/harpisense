import {test} from 'node:test';
import assert from 'node:assert/strict';
import {installationSnapshot,parseSetupProgress,readInstallation} from '../src/installation-state.ts';

const setup={version:0,document:null,state:'not_started',operational:false,pending:[]};
const current={desired_revision:0,effective_revision:null,state:'not_started',proposed_status:null,operational:false};
const applied={...current,desired_revision:2,effective_revision:2,state:'applied_verified',proposed_status:'APPLIED',effective:{parameters:{timezone:'America/Sao_Paulo',display_name:'Laboratório'}},presentation:{verified:true}};
const draft={...setup,version:3,state:'draft_saved',document:{step:'mqtt',parameters:{display_name:'Laboratório',timezone:'America/Sao_Paulo'}}};

test('cloud planning is optional and cannot assert connectivity or carry credentials',()=>{
 const cloud={mode:'draft',provider:'azure_blob',destination:'oficina/backup',include:['configuration'],periodicity:'weekly',retention_days:30};
 assert.equal(parseSetupProgress({...draft,document:{...draft.document,cloud_backup:cloud}}).document?.cloud_backup?.provider,'azure_blob');
 assert.equal(parseSetupProgress({...draft,document:{...draft.document,cloud_backup:{mode:'deferred'}}}).document?.cloud_backup?.mode,'deferred');
 for(const invalid of [{...cloud,provider:'unknown'},{...cloud,password:'example'},{...cloud,destination:'https://cloud.invalid/?token=example'},{...cloud,retention_days:0}])
  assert.throws(()=>parseSetupProgress({...draft,document:{...draft.document,cloud_backup:invalid}}));
});

test('new requires no saved draft and no configuration revision',()=>{
 assert.equal(installationSnapshot(setup,current).status,'new');
 assert.equal(installationSnapshot(draft,current).status,'pending');
 assert.equal(installationSnapshot(setup,{...current,desired_revision:1}).status,'pending');
 assert.equal(installationSnapshot(setup,{...current,effective_revision:1}).status,'pending');
});
test('saved, validated, applying and failed revisions remain pending',()=>{
 for(const state of ['draft_saved','validated','application_pending','failed'])
  assert.equal(installationSnapshot(draft,{...applied,state}).status,'pending');
 assert.equal(installationSnapshot(draft,{...applied,desired_revision:3}).status,'pending');
 assert.equal(installationSnapshot(draft,{...applied,presentation:{verified:false}}).status,'pending');
});
test('confirmed application completes only its scope, independently of operational readiness',()=>{
 const result=installationSnapshot(draft,applied);
 assert.equal(result.status,'completed');
 assert.equal(result.current.operational,false);
 assert.equal(installationSnapshot(setup,applied).status,'completed');
 assert.equal(installationSnapshot({...draft,document:{...draft.document,parameters:{display_name:'Nova edição'}}},applied).status,'pending');
});
test('malformed or inconsistent progress is failure, never a new installation',()=>{
 for(const value of [null,{}, {...setup,version:-1},{...setup,version:1},{...setup,document:{}},
  {...draft,document:{step:'unknown',parameters:{}}},{...draft,document:{step:'mqtt',parameters:null}},
  {...draft,document:{...draft.document,devices:[{}]}},{...setup,pending:[null]}])
  assert.throws(()=>parseSetupProgress(value));
 assert.throws(()=>installationSnapshot(setup,{operational:false}));
});
test('only reads the two existing configuration endpoints and preserves failed queries',async()=>{
 const calls:string[]=[];
 const client={get:async(path:string)=>{calls.push(path);return path.endsWith('/setup')?draft:current}};
 assert.equal((await readInstallation(client)).setup.document?.step,'mqtt');
 assert.deepEqual(calls,['/api/v1/config/setup','/api/v1/config/current']);
 await assert.rejects(readInstallation({get:async()=>{throw new Error('offline')}}),/offline/);
});
