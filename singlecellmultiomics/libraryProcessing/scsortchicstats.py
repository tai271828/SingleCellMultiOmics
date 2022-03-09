#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import os
import argparse
import pysam
import json
from multiprocessing import Pool

def count_reads(args):
    bam, contig = args
    passreads = 0
    qcfailreads, duplicate_reads = 0, 0
    with pysam.AlignmentFile(bam) as al:
        for read in al.fetch(contig):
            if read.is_qcfail:
                qcfailreads+=1
            elif read.is_duplicate:
                duplicate_reads+=1
            else:
                passreads+=1
    return contig, passreads, qcfailreads, duplicate_reads


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Obtain statistics for scSort-ChIC libraries')
    argparser.add_argument('bam',type=str, help='Path to tagged bam file')

    argparser.add_argument('featurebeds',type=str, nargs='+', help='Path to feature coverage bed files')

    argparser.add_argument('-o',type=str, help='Path to output json file')
    argparser.add_argument('-t',type=int, help='Threadcount')

    args = argparser.parse_args()



    # df_alignments = pd.DataFrame([ [(int(x) if i>0 else x) for i,x in enumerate(r.split('\t'))] for r in pysam.idxstats(args.bam).split('\n')])
    # df_alignments = df_alignments.set_index(0)

    cnts = dict() # pass read counts
    qcfailreads, duplicatereads = 0, 0
    with pysam.AlignmentFile(args.bam) as al:
        with Pool(args.t) as workers:
            for contig, passreads, _qcfailreads, _duplicatereads in workers.imap_unordered( count_reads, ((args.bam,contig) for contig in al.references)):
                cnts[contig] = passreads #dict(workers.imap_unordered( count_reads, ((args.bam,contig) for contig in al.references)))
                qcfailreads += _qcfailreads
                duplicatereads += _duplicatereads
    cnts = pd.Series( cnts )
    passreads = cnts.sum()

    totals = {}
    for path in args.featurebeds:
        df = pd.read_csv(path,delimiter='\t',header=None)
        df.columns=['contig','start','end','obs']
        totals[path.split('_')[-2]] = df['obs'].sum()

    scaffold_coverage = pd.Series({
        name:float(100*cnts[scaffold]/passreads) for name, scaffold in
        [('Cutibacterium','CP025935.1'),
         ('E. coli RHB09-C15','CP057942.1'),
         ('E. coli K-12','NC_000913.3'),
         ('E. coli Lambda Phage','J02459.1'),
         ('Mitochondrial','MT')
        ]
    }).to_dict()

    d = {
        'feature_coverage': {k:float(v) for k,v in (100*pd.Series(totals)/passreads).to_dict().items()},
        'scaffold_coverage':scaffold_coverage,
        'passreads':int(passreads),
        'duplicatereads': duplicatereads,
        'qcfailreads': qcfailreads,
        'totalreads': passreads+duplicatereads+qcfailreads
        }

    with open(args.o,'w') as o:
        json.dump(d, o, indent=2)
