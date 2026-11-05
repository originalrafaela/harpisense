"""CLI: referência persistente e explicações de contratos ou janelas JSON."""
import argparse
import json
from pathlib import Path
from .core import load_model,create_reference,explain,detection
from .reports import write_results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    bg=commands.add_parser('background')
    bg.add_argument('--model',required=True); bg.add_argument('--training')
    bg.add_argument('--max-rows',type=int,default=64); bg.add_argument('--seed',type=int,default=42)
    bg.add_argument('--out',required=True)
    exp=commands.add_parser('explain')
    exp.add_argument('--model',required=True);exp.add_argument('--background',required=True)
    inputs=exp.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--detection',help='Contrato detection JSON já emitido')
    inputs.add_argument('--window',help='Uma janela JSON com timestamps e sensor_id')
    exp.add_argument('--target-class');exp.add_argument('--permutations',type=int,default=32)
    exp.add_argument('--seed',type=int,default=42);exp.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        b=load_model(args.model)
        if args.command=='background':
            ref=create_reference(b,training=args.training,max_rows=args.max_rows,seed=args.seed)
            p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('x',encoding='utf-8') as f: json.dump(ref,f,indent=2,ensure_ascii=False,allow_nan=False)
            print(p)
        else:
            ref=json.loads(Path(args.background).read_text())
            record=json.loads(Path(args.detection or args.window).read_text())
            if args.window: record=detection(b,record)
            if Path(args.out).exists(): raise ValueError('Diretório de saída já existe; escolha outro')
            result,diagnostics=explain(b,ref,record,target_class=args.target_class,permutations=args.permutations,seed=args.seed)
            write_results(args.out,record,result,diagnostics)
            print(args.out)
    except (ValueError,KeyError,OSError,TypeError) as exc:
        parser.exit(2,f'Erro: {exc}\n')

if __name__=='__main__': main()
