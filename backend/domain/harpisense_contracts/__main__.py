import argparse,json
from pathlib import Path
from .validation import validate,validate_links,ContractError
from .schema_source import export

def strict_json(path):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ContractError('Chave JSON duplicada: '+k)
            result[k]=v
        return result
    def invalid(value): raise ContractError('Constante JSON nao finita: '+value)
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=invalid)

def main():
    p=argparse.ArgumentParser(description='Validar registros ou grafo de contratos HarpiSense')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['validate','validate-bundle']:
        q=sub.add_parser(name);q.add_argument('input')
    q=sub.add_parser('export-schemas');q.add_argument('directory')
    args=p.parse_args()
    try:
        if args.command=='export-schemas': export(args.directory)
        elif args.command=='validate': validate(strict_json(args.input))
        else:
            bundle=strict_json(args.input)
            if set(bundle)!=set(['detections','explanations','incidents','decisions']): raise ContractError('Chaves do bundle invalidas')
            validate_links(**bundle)
        print('OK');return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('INVALID: '+str(exc));return 2

if __name__=='__main__': raise SystemExit(main())
