"""Worker JSONL com outbox SQLite persistente. Saída tem entrega ao menos uma vez."""
import argparse
import hashlib
import json
import sqlite3
import sys


class Worker:
    def __init__(self, bundle, database, signal_builder):
        self.signal_builder=signal_builder
        self.bundle=bundle
        self.db=sqlite3.connect(database)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (key TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()

    def close(self): self.db.close()

    def process(self, window, *, now=None):
        identity=[self.bundle['model_version'],window['collection_session_id'],window['window_id']]
        key=hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        raw=json.dumps(window,sort_keys=True,allow_nan=False)
        digest=hashlib.sha256(raw.encode()).hexdigest()
        # Transação serializa concorrência entre processos usando o mesmo banco.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            prior=self.db.execute('SELECT digest,payload FROM outbox WHERE key=?',(key,)).fetchone()
            if prior:
                if prior[0]!=digest: raise ValueError('identifier_conflict')
                signal=json.loads(prior[1])
                # Refaz validade temporal: uma retransmissão antiga não renova evidência.
                refreshed=self.signal_builder(self.bundle,window,now=now)
                for field in ['status','eligible_for_correlation','age_seconds','generated_at']:
                    signal[field]=refreshed[field]
                return {**signal,'duplicate':True}
            signal=self.signal_builder(self.bundle,window,now=now)
            self.db.execute('INSERT INTO outbox VALUES (?,?,?)',(key,digest,json.dumps(signal,allow_nan=False)))
        return {**signal,'duplicate':False}


def run_cli(load_bundle,signal_builder,signal_schema):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True); p.add_argument('--state',required=True)
    a=p.parse_args(); worker=Worker(load_bundle(a.model),a.state,signal_builder)
    errors=0
    try:
        for line in sys.stdin:
            try:
                if not line.strip(): continue
                signal=worker.process(json.loads(line))
            except (ValueError,TypeError,KeyError) as exc:
                errors+=1
                signal={'signal_schema_version':signal_schema,
                    'status':'invalid_data','eligible_for_correlation':False,
                    'block_authorized':False,'error':str(exc)}
            print(json.dumps(signal,allow_nan=False),flush=True)
    finally: worker.close()
    return 2 if errors else 0

