#!/bin/python
# This script will ...
#
#
#
# Abin Abraham
# created on: 2020-02-13 09:22:14

import os
import sys
import time
import numpy as np
import pandas as pd
from datetime import datetime

import matplotlib.pyplot  as plt

DATE = datetime.now().strftime('%Y-%m-%d')

sys.path.append("/scratch/abraha1/gsel_/gsel_pipeline_vec/")
from ld_expand_all_control_sets import load_ld_df, force_ld_control_snps

sys.path.append("/dors/capra_lab/projects/gwas_allele_age_evolution/scripts/pipeline")
from helper_general import Outputs


import logging
logger = logging.getLogger('main.{}'.format(__name__))


# -----------
# FUNCTIONS
# -----------

def parse_input_args():


    # TODO: delete (only for dev purposes)
    if len(sys.argv) != 7:

        print("running dev arguments ... delete later")
        root="/scratch/abraha1/gsel_/gsel_pipeline_vec/test/bmi_small_vec"
        snpsnap_db_file="/dors/capra_lab/projects/gwas_allele_age_evolution/scripts/pipeline/dev/gsel_pipeline_vec/snpsnap_database/ld0.1_collection.tab.pickle"
        ld_expanded_control_sets_file= os.path.join(root, 'giant_bmi_small_ld_expand_control_snps/ld_expanded_all_control_sets.tsv')
        lead_snps_ld_counts_file=os.path.join(root, 'giant_bmi_small_clump/lead_gwas_snps_with_ldsnps_counts.txt')
        ld_expanded_control_sets_r2_file = os.path.join(root, "giant_bmi_small_ld_expand_control_snps/r2_ld_expanded_all_control_sets.tsv")
        ldbuds_r2_threshold="friends_ld05"
        output_root=root
        analysis_name="dev_vec"


    else:

        # TODO: convert all args to requried args

        parser = argparse.ArgumentParser(description='Run expand control set.')

        parser.add_argument('snpsnap_db_file',
                            action='store', type=str,
                            help="tsv of snpsnap database at a specific r2 threshold defining a 'locus' ")

        parser.add_argument('ld_expanded_control_sets_file',
                            action='store', type=str,
                            help='tsv of ld expanded control snps')

        parser.add_argument('lead_snps_ld_counts_file',
                            action='store', type=str,
                            help='tsv of # of ld snps required for each input/lead gwas snp')

        parser.add_argument('ld_expanded_control_sets_r2_file',
                            action='store', type=str,
                            help='tsv of r2 values of ld expanded control snps')

        parser.add_argument('ldbuds_r2_threshold',
                            action='store', type=int,
                            help='column name from which to select from in the snpsnap db indicating the ld buddies r2 threshold')

        parser.add_argument('output_root',
                            action='store', type=str,
                            help="output_dir")


        parser.add_argument('analysis_name',
                            action='store', type=str,
                            help="the name of this analysis")


        # retrieve passed arguments
        args = parser.parse_args()
        snpsnap_db_file = args.snpsnap_db_file
        ld_expanded_control_sets_file = args.ld_expanded_control_sets_file
        lead_snps_ld_counts_file = args.lead_snps_ld_counts_file
        ld_expanded_control_sets_r2_file = args.ld_expanded_control_sets_r2_file
        ldbuds_r2_threshold = args.ldbuds_r2_threshold
        output_root = args.output_root
        analysis_name = args.analysis_name




    return snpsnap_db_file, ld_expanded_control_sets_file, lead_snps_ld_counts_file, ld_expanded_control_sets_r2_file, ldbuds_r2_threshold, output_root, analysis_name

def summarize_across_sets(match_param_col, lead_snps_only_df, control_sets_df, db, control_cols):


    summary_df = pd.DataFrame()
    for index, row in lead_snps_only_df.iterrows():

        temp_df = db.loc[db.snpID.isin(row.loc[control_cols].values), match_param_col].describe().reset_index().rename(columns={match_param_col:row.lead_snp}).set_index('index').transpose()
        summary_df = summary_df.append(temp_df)


    summary_df.columns.name=""
    summary_df.reset_index(inplace=True)
    summary_df.rename(columns={'index':'lead_snp'},inplace=True)

    lead_snps = lead_snps_only_df.lead_snp.unique()
    lead_maf_df = db.loc[db.snpID.isin(lead_snps), ['snpID', match_param_col]].copy()

    uniq_counts = get_uniq_control_snps(control_sets_df,lead_snps_only_df).loc[:, ['lead_snp','num_uniq_control_snps','percent_matched']]

    # add lead snp maf
    temp_summary_df =  pd.merge(summary_df, lead_maf_df, left_on='lead_snp', right_on='snpID', how='inner').rename(columns={match_param_col:'lead_snp_{}'.format(match_param_col), 'count':'num_control_sets'}).drop('snpID', axis=1)
    final_summary_df = pd.merge(temp_summary_df, uniq_counts, on='lead_snp', how='inner')

    final_summary_df = final_summary_df.loc[:,['lead_snp','num_control_sets','num_uniq_control_snps', 'percent_matched','lead_snp_{}'.format(match_param_col),  'mean', 'std', 'min', '25%', '50%', '75%', 'max']].copy()

    assert final_summary_df.shape[0] == lead_snps_only_df.shape[0], "# lead snps at the end does not equal what you started with :O "


    mean_std_df = final_summary_df.loc[:, ['lead_snp', 'lead_snp_{}'.format(match_param_col), 'mean','std']].copy()
    mean_std_df['mean'] = mean_std_df['mean'].apply(lambda x: np.around(x, 3))
    mean_std_df['std'] = mean_std_df['std'].apply(lambda x: np.around(x, 3))
    mean_std_df.rename(columns={'mean':'mean_control_{}'.format(match_param_col),'std':'std_control_{}'.format(match_param_col)},inplace=True)


    mean_std_df['upper_sd'] = mean_std_df['mean_control_{}'.format(match_param_col)] + mean_std_df['std_control_{}'.format(match_param_col)]
    mean_std_df['lower_sd'] = mean_std_df['mean_control_{}'.format(match_param_col)] - mean_std_df['std_control_{}'.format(match_param_col)]
    mean_std_df['outside_sd_{}'.format(match_param_col)] = (mean_std_df['lead_snp_{}'.format(match_param_col)] > mean_std_df['upper_sd']) & (mean_std_df['lead_snp_{}'.format(match_param_col)] < mean_std_df['lower_sd'])
    mean_std_df.drop(['upper_sd','lower_sd'], axis=1, inplace=True)

    return final_summary_df, mean_std_df

def get_uniq_control_snps(control_sets_df,lead_snps_only_df ):

    # how many unique control snps are there?
    uniq_controls_df = control_sets_df.transpose().nunique().reset_index().set_index(lead_snps_only_df.lead_snp, drop=True)
    uniq_controls_df.drop('index', axis=1, inplace=True)
    uniq_controls_df.columns = ['num_uniq_control_snps']
    uniq_controls_df.reset_index(inplace=True)
    uniq_controls_df['num_requested'] = control_sets_df.shape[1]
    uniq_controls_df['percent_matched'] =  uniq_controls_df.num_uniq_control_snps / uniq_controls_df.num_requested


    return uniq_controls_df

def check_chrom(lead_and_control_sets_df, control_cols):
    temp_lead_df = lead_and_control_sets_df.loc[:, 'lead_snp'].copy()
    temp_chrom_only_df = lead_and_control_sets_df.loc[:, control_cols].applymap(lambda x: x.split(":")[0]).copy()
    lead_chrom_only_df = pd.concat( (temp_lead_df, temp_chrom_only_df),axis=1)
    lead_chrom_only_df[lead_chrom_only_df == "None"] = np.nan
    uniq_chrom_per_lead_df = lead_chrom_only_df.groupby('lead_snp').nunique().drop('lead_snp', axis=1)

    return uniq_chrom_per_lead_df

def make_ldscore_df(og_control_sets_df, og_ld_df, control_cols ):

    # note: control_sets_df contains both lead and control snps info
    control_sets_df = og_control_sets_df.copy()
    control_sets_df.sort_values(['lead_snp','lead_snp_bool','R2'], ascending=False, inplace=True)

    # preallocate
    ld_pair_list_df = control_sets_df.loc[ control_sets_df['lead_snp_bool']==True, ['lead_snp']+control_cols].copy()
    ld_pair_list_df.loc[:, control_cols] = np.nan


    # forced_ld_df = force_ld_control_snps(ld_df, control_snps)
    for lead_snp in control_sets_df.lead_snp.unique():

        csnps_for_isnp=control_sets_df.loc[(control_sets_df['lead_snp'] == lead_snp) & (control_sets_df['lead_snp_bool']==True), control_cols ].values.tolist()[0]
        ldexp_csnps_for_isnp=control_sets_df.loc[(control_sets_df['lead_snp'] == lead_snp) & (control_sets_df['lead_snp_bool']==False), control_cols ].values.tolist()

        this_lead_df = control_sets_df.loc[(control_sets_df['lead_snp'] == lead_snp),:].copy()

        for control_col in control_cols:
            all_snps = this_lead_df.loc[:, control_col].tolist()
            lead_control_snp, ld_snps = all_snps[0], all_snps[1:]
            pairs = ["{}_{}".format(lead_control_snp,lead_control_snp)] + ["{}_{}".format(lead_control_snp, ldsnp) for ldsnp in ld_snps]

            ld_pair_list_df.loc[ld_pair_list_df['lead_snp']== lead_snp, control_col] = [pairs]

    # format ld_df
    ld_df = og_ld_df.copy()
    ld_df['A_B'] = ld_df['SNP_A'] + "_" + ld_df['SNP_B']
    ld_df['B_A'] = ld_df['SNP_B'] + "_" + ld_df['SNP_A']
    ld_df.drop(['CHR_A','BP_A','SNP_A','CHR_B','BP_B','SNP_B','DP'], axis=1, inplace=True)

    # calc r2 sum for ld snp
    sum_r2 = lambda x : ld_df.loc[ (ld_df.A_B.isin(x)) | (ld_df.B_A.isin(x))].drop_duplicates(subset=['A_B','B_A']).R2.sum()
    ld_pair_list_df.set_index('lead_snp',inplace=True)
    ldr2_df =ld_pair_list_df.applymap(sum_r2)

    control_r2_sum_df = ldr2_df.reset_index()
    lead_r2_sum_df = control_sets_df.groupby('lead_snp')['R2'].sum().reset_index()

    ldscore_df = pd.merge(lead_r2_sum_df, control_r2_sum_df, on="lead_snp", how='inner')

    return ldscore_df

def plot():
    # under dev
    # %%
    label='MAF'
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10,8))
    ax.errorbar(x = maf_mean_std_df.lead_snp, y=maf_mean_std_df.mean_control_snp_maf, yerr=maf_mean_std_df.std_control_snp_maf, marker='.', elinewidth=1, linewidth=0, capsize=4, color='black', alpha=0.9)
    plt.plot(maf_mean_std_df.lead_snp_snp_maf, marker='o', color='r', markersize=4, linewidth=0,)
    plt.xticks(rotation=325, ha='left', va='top', fontsize=20)
    plt.yticks(fontsize=20)
    plt.xlabel('GWAS Lead SNPs', fontsize=20)
    plt.ylabel('{}'.format(label), fontsize=20)
    plt.title("{} of LD Expanded Control Sets compared to Lead SNP locus".format(label), fontsize=20)

def combine_summary_dfs(summary_maf_df,maf_mean_std_df, gcount_mean_std_df, dist_mean_std_df, ldbuds_mean_std_df ):

    counts_df = summary_maf_df.loc[:, ['lead_snp','num_control_sets','num_uniq_control_snps','percent_matched']].copy()

    combined_summary_df = pd.merge(
                pd.merge(
                pd.merge(pd.merge(counts_df, maf_mean_std_df, on='lead_snp', how='outer'), gcount_mean_std_df, on='lead_snp', how='outer'),
                                        dist_mean_std_df, on='lead_snp', how='outer'),
                                        ldbuds_mean_std_df, on='lead_snp', how='outer')

    return combined_summary_df


def set_up_outputs(OutputObj):

    # set up ouput files
    OutputObj.add_output('lead_snps_matching_quality_file', 'lead_snps_matching_quality.tsv', add_root=True)
    OutputObj.add_output('ldscore_for_expanded_control_sets_quality_file', 'ldscore_matching_quality_for_ldexpanded_sets.tsv', add_root=True)

    return OutputObj


def summarize_ldscore(r2_df, control_cols):

    ldscore_df = r2_df.loc[:, ['lead_snp']+control_cols].groupby('lead_snp')[control_cols].apply(lambda df: df.sum(skipna=True)).reset_index()
    ldscore_df['mean_ldscore_across_sets'] = ldscore_df.loc[:, control_cols].mean(1)
    ldscore_df['std_ldscore_across_sets'] = ldscore_df.loc[:, control_cols].std(1)
    ldscore_df['num_sets'] = len(control_cols)
    ldscore_df = ldscore_df.round(2)

    lead_ldscore_df = r2_df.loc[:, ['lead_snp','R2']].groupby('lead_snp').sum().reset_index()
    lead_ldscore_df.rename(columns={'R2':'ldscore'}, inplace=True)
    lead_control_ldscore_df = pd.merge(lead_ldscore_df, ldscore_df.loc[:, ['lead_snp','mean_ldscore_across_sets','std_ldscore_across_sets','num_sets']], on='lead_snp',how='outer')



    lead_control_ldscore_df['upper_sd'] = lead_control_ldscore_df['mean_ldscore_across_sets'] + lead_control_ldscore_df['std_ldscore_across_sets']
    lead_control_ldscore_df['lower_sd'] = lead_control_ldscore_df['mean_ldscore_across_sets'] - lead_control_ldscore_df['std_ldscore_across_sets']
    lead_control_ldscore_df['ldscore_outside_sd'] = (lead_control_ldscore_df['ldscore'] > lead_control_ldscore_df['upper_sd']) & (lead_control_ldscore_df['ldscore']< lead_control_ldscore_df['lower_sd'])

    return lead_control_ldscore_df

def check_ld_expanded_sets(snpsnap_db_file, ld_expanded_control_sets_file , lead_snps_ld_counts_file, ld_expanded_control_sets_r2_file, ldbuds_r2_threshold, output_root, analysis_name):
    # note:
    #       ldbuds_r2_threshold must be in ''


    check_start = time.time()


    # set up outputs
    logger.info("Analyzing LD expanded control sets...")
    output_dir = os.path.join(output_root, '{}_check_ld_expand_control_snps'.format(analysis_name))
    OutObj = Outputs(output_dir, overwrite=True)
    OutObj = set_up_outputs(OutObj)



    ###
    ###   load
    ###

    # load ld database
    db = pd.read_pickle(snpsnap_db_file)

    # load ld counts and control sets
    ld_counts_df = pd.read_csv(lead_snps_ld_counts_file, sep="\t")
    lead_and_control_sets_df = pd.read_csv(ld_expanded_control_sets_file, sep="\t")

    # create subsets
    lead_snps_only_df = lead_and_control_sets_df.loc[lead_and_control_sets_df['lead_snp_bool']==True].copy()
    control_sets_of_lead_snps_only_df = lead_and_control_sets_df.loc[lead_and_control_sets_df['lead_snp_bool']==True, lead_and_control_sets_df.columns.difference(['lead_snp','ld_snp','R2','lead_snp_bool'])].copy()
    control_sets_df = lead_and_control_sets_df.loc[:, lead_and_control_sets_df.columns.difference(['lead_snp','ld_snp','R2','lead_snp_bool'])].copy()


    n_control_sets = control_sets_df.shape[1]
    control_cols = ["Set_{}".format(num) for num in np.arange(1, n_control_sets +1)]



    ###
    ###   summarize for lead snps only and their matched control snps
    ###

    summary_maf_df, maf_mean_std_df = summarize_across_sets('snp_maf',lead_snps_only_df,control_sets_of_lead_snps_only_df, db, control_cols)
    summary_gcount_df,  gcount_mean_std_df  = summarize_across_sets('gene_count',lead_snps_only_df,control_sets_of_lead_snps_only_df, db, control_cols)
    summary_dist_gene_df,  dist_mean_std_df  = summarize_across_sets('dist_nearest_gene',lead_snps_only_df,control_sets_of_lead_snps_only_df, db, control_cols)
    summary_ldbuds_df,  ldbuds_mean_std_df  = summarize_across_sets(ldbuds_r2_threshold,lead_snps_only_df, control_sets_of_lead_snps_only_df,db, control_cols)


    # check if any properties lie outside of 1 S.D
    maf_bool = maf_mean_std_df['outside_sd_snp_maf'].any()
    gene_count_bool = gcount_mean_std_df['outside_sd_gene_count'].any()
    dist_bool = dist_mean_std_df['outside_sd_dist_nearest_gene'].any()
    ldbuds_bool = ldbuds_mean_std_df['outside_sd_{}'.format(ldbuds_r2_threshold)].any()

    assert ~any([maf_bool, gene_count_bool, dist_bool, ldbuds_bool]), "WARNING!: Matching properties for lead snps outside 1 S.D. of control sets!\n Check {}".format(lead_snps_matching_quality_file)

    combined_summary_df = combine_summary_dfs(summary_maf_df,maf_mean_std_df, gcount_mean_std_df, dist_mean_std_df, ldbuds_mean_std_df )
    combined_summary_df.to_csv(OutObj.get('lead_snps_matching_quality_file'), sep="\t", index=False)
    logger.info("Wrote summary of matching quality to: {}".format(OutObj.get('lead_snps_matching_quality_file')))



    ###
    ### summarize across ld expanded sets
    ###

    # -----------
    # check that chromosomes are the same in each control set for a given lead snp
    # -----------
    uniq_chrom_per_lead_df = check_chrom(lead_and_control_sets_df, control_cols)


    if (uniq_chrom_per_lead_df == 1).all(1).all():
        logger.info("For each input/lead gwas snp, the ld expanded control snps are on the same chromosome.")
    else:
        logger.info("WARNING... there are difference chromosomes for a given set of ld expanded control snps.")


    # -----------
    # calcualte LD SCORE based on the lead snp
    # -----------
    r2_df = pd.read_csv(ld_expanded_control_sets_r2_file, sep="\t", low_memory=False)
    r2_df.replace('None', np.nan, inplace=True)
    r2_df.loc[:,control_cols] = r2_df.loc[:,control_cols].apply(pd.to_numeric)

    lead_control_ldscore_df = summarize_ldscore(r2_df, control_cols)


    if lead_control_ldscore_df.ldscore_outside_sd.any():
        logger.info("* Warning: ldscore range for ld expanded control sets are not within 1 SD of the input/lead locus")
    else:
        logger.info("LDscore range for ld expanded control sets ARE WITHIN 1 SD of the input/lead locus")

    lead_control_ldscore_df.to_csv(OutObj.get('ldscore_for_expanded_control_sets_quality_file'), sep="\t", index=False)
    logger.info("Wrote LDscore summary to: {}".format(OutObj.get('ldscore_for_expanded_control_sets_quality_file')))
    logger.info("Done checking the ld-expanded control sets. Took {:.2f} minutes".format( (time.time() - check_start)/60))

    return combined_summary_df, lead_control_ldscore_df


# -----------
# MAIN
# -----------

if __name__ == "__main__":
    snpsnap_db_file, ld_expanded_control_sets_file, lead_snps_ld_counts_file, ld_expanded_control_sets_r2_file, ldbuds_r2_threshold, output_dir, analysis_name = parse_input_args()
    _ = check_ld_expanded_sets(snpsnap_db_file, ld_expanded_control_sets_file , lead_snps_ld_counts_file, ld_expanded_control_sets_r2_file, ldbuds_r2_threshold, output_dir, analysis_name)