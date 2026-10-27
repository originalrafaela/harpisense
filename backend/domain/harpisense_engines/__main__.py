import argparse,json
from pathlib import Path
from .core import decide
from harpisense_contracts.__main__ import strict_json

def main():
    p=argparse.ArgumentParser(description='Avaliação offline de contexto confiável; não executa contenção')
    p.add_argument('--context',required=True);p.add_argument('--mode',type=int,required=True)
    p.add_argument('--now',required=True,help='Timestamp UTC explícito para reprodução')
    p.add_argument('--config');p.add_argument('--proposal');p.add_argument('--out',required=True)
    a=p.parse_args()
    read=lambda s:None if s is None else strict_json(s)
    try:
        result=decide(read(a.context),mode=a.mode,now=a.now,config=read(a.config),proposal=read(a.proposal))
        with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
        print(result['decision']['status'])
    except (ValueError,KeyError,TypeError,OSError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
