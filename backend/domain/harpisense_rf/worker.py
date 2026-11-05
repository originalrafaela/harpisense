"""Entrypoint compatível; estado/outbox implementados em harpisense_data.worker."""
from harpisense_data.worker import Worker as BaseWorker,run_cli
from .integracao import risk_signal
from .random_forest import load_bundle
class Worker(BaseWorker):
    def __init__(self,bundle,database):super().__init__(bundle,database,risk_signal)
def main():return run_cli(load_bundle,risk_signal,'harpisense.detection.rf.v1')
if __name__=='__main__':raise SystemExit(main())
