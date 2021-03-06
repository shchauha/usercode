"""
Plot 
"""
import sys
import os
import re
import math
import uuid
import copy
import imp
from array import array
import random
import collections
import pickle
import time

# Parse command-line options
from argparse import ArgumentParser

def parseArgs() :
    p = ArgumentParser()
    p.add_argument('--fileName',     default='ntuple.root',  dest='fileName',        help='( Default ntuple.root ) Name of files')
    p.add_argument('--treeName',     default='events'     ,  dest='treeName',        help='( Default events ) Name tree in root file')
    p.add_argument('--samplesConf',  default=None,           dest='samplesConf',     help=('Use alternate sample configuration. '
                                                                                           'Must be a python file that implements the configuration '
                                                                                           'in the same manner as in the main() of this script.  If only '
                                                                                           'the file name is given it is assumed to be in the same directory '
                                                                                           'as this script, if a path is given, use that path' ) )

    p.add_argument('--samplesConfGG',  default=None,           dest='samplesConfGG',     help='Use alternate sample configuration for diphoton events. '  )
    p.add_argument('--samplesConfWgg',  default=None,           dest='samplesConfWgg',     help='Use alternate sample configuration for fake-fake templates. '  )
    
                                                                                           
    p.add_argument('--xsFile',     default=None,  type=str ,        dest='xsFile',         help='path to cross section file.  When calling AddSample in the configuration module, set useXSFile=True to get weights from the provided file')
    p.add_argument('--lumi',     default=None,  type=float ,        dest='lumi',         help='Integrated luminosity (to use with xsFile)')
    p.add_argument('--outputDir',     default=None,  type=str ,        dest='outputDir',         help='output directory for histograms')
    p.add_argument('--readHists',     default=False,action='store_true',   dest='readHists',         help='read histograms from root files instead of trees')
    p.add_argument('--quiet',     default=False,action='store_true',   dest='quiet',         help='disable information messages')
    p.add_argument('--syst_file',     default=None,  type=str ,        dest='syst_file',         help='Location of systematics file')
    p.add_argument('--ptbins',     default=None,  type=str ,        dest='ptbins',         help='Comma separated list of pt bins')
    p.add_argument('--fitvar',     default='sigmaIEIE',  type=str ,        dest='fitvar',         help='Variable to fit, sigmaIEIE, chIsoCorr,neuIsoCorr,phoIsoCorr')
    p.add_argument('--ffcorr',     default='None',  type=str ,        dest='ffcorr',         help='Do ff correlated templates, None, nom, loose, tight')
    p.add_argument('--sublptbins',     default=None,  type=str ,        dest='sublptbins',         help='Comma separated list of sublead pt bins')
    p.add_argument('--zgg',     default=False,  action='store_true',        dest='zgg',         help='use zgg samples, etc')
    
    
    p.add_argument('--channels', default=None,  dest='channels', help='comma separated list of channels to run' )
    
    return p.parse_args()

import ROOT
from uncertainties import ufloat
from uncertainties import unumpy
from SampleManager import SampleManager
from SampleManager import Sample
from SampleManager import DrawConfig

_DISABLE_TEMPLATE_SAVE = True

common_ptbins = [15, 25, 40, 70, 1000000 ]
options=None
_sieie_cuts  = { 'EB' : (0.011,0.029), 'EE' : (0.033, 0.087) }
_chIso_cuts  = { 'EB' : (1.5, 19.5)  , 'EE' : (1.2,20.4) }
#_chIso_cuts  = { 'EB' : (1.5, 15.0)  , 'EE' : (1.2,15.6) }
_neuIso_cuts = { 'EB' : (1.0,20)     , 'EE' : (1.5,20.5) }
_phoIso_cuts = { 'EB' : (0.7,20.3)   , 'EE' : (1.0,20) }

_var_cuts = {}
_var_cuts['sigmaIEIE'] = _sieie_cuts
_var_cuts['chIsoCorr'] = _chIso_cuts
_var_cuts['neuIsoCorr'] = _neuIso_cuts
_var_cuts['phoIsoCorr'] = _phoIso_cuts

_mgg_cut = ''
#_mgg_cut = '&& m_ph1_ph2 > 120 && m_ph1_ph2 < 240'

global _nmatrix_calls
_nmatrix_calls = 0

def get_default_binning(var='sigmaIEIE') :

    if var == 'sigmaIEIE' :
        return { 'EB' : (30, 0, 0.03), 'EE' : (30, 0, 0.09) }
    elif var == 'chIsoCorr' :
        return { 'EB' : (30, 0, 45), 'EE' : (35, 0, 42) }
    elif var == 'neuIsoCorr' :
        return { 'EB' : (40, -2, 38), 'EE' : (30, -2, 43) }
    elif var == 'phoIsoCorr' :
        return { 'EB' : (53, -2.1, 35), 'EE' : (42, -2, 40) }

def get_template_draw_strs( var, ch, eleVeto, iso_vals ) :

    # in the muon channel remove the pixel seed veto
    varstr = ''
    phstr = ''
    if iso_vals is None :
        if ch == 'mu' or ch=='muhighmt' or ch =='mulowmt' :
            if var == 'sigmaIEIE' :
                varstr = 'ph_mediumNoSIEIENoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoEleVeto_idx'
            elif var == 'chIsoCorr' :
                varstr = 'ph_mediumNoChIsoNoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoChIsoNoEleVeto_idx'
            elif var == 'neuIsoCorr' :
                varstr = 'ph_mediumNoNeuIsoNoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoNeuIsoNoEleVeto_idx'
            elif var == 'phoIsoCorr' :
                varstr = 'ph_mediumNoPhoIsoNoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoPhoIsoNoEleVeto_idx'
            else :
                return None, None
        else :
            if var == 'sigmaIEIE' :
                varstr = 'ph_mediumNoSIEIE%s_n'%eleVeto
                phstr = 'ptSorted_ph_mediumNoSIEIE%s_idx'%eleVeto
            elif var == 'chIsoCorr' :
                varstr = 'ph_mediumNoChIso%s_n'%eleVeto
                phstr = 'ptSorted_ph_mediumNoChIso%s_idx'%eleVeto
            elif var == 'neuIsoCorr' :
                varstr = 'ph_mediumNoNeuIso%s_n'%eleVeto
                phstr = 'ptSorted_ph_mediumNoNeuIso%s_idx'%eleVeto
            elif var == 'phoIsoCorr' :
                varstr = 'ph_mediumNoPhoIso%s_n'%eleVeto
                phstr = 'ptSorted_ph_mediumNoPhoIso%s_idx'%eleVeto
            else :
                return None, None
    elif isinstance( iso_vals, str ) :
        if ch == 'mu' or ch=='muhighmt' or ch =='mulowmt' :
            if var == 'sigmaIEIE' :
                varstr = 'ph_mediumNoSIEIENoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoEleVeto_idx'
            elif var == 'chIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoChIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoChIso_idx'
            elif var == 'neuIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoNeuIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoNeuIso_idx'
            elif var == 'phoIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoPhoIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoPhoIso_idx'
            else :
                return None, None
        else :
            if var == 'sigmaIEIE' :
                varstr = 'ph_mediumNoSIEIENoEleVeto_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoEleVeto_idx'
            elif var == 'chIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoChIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoChIso_idx'
            elif var == 'neuIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoNeuIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoNeuIso_idx'
            elif var == 'phoIsoCorr' :
                varstr = 'ph_mediumNoSIEIENoPhoIso_n'
                phstr = 'ptSorted_ph_mediumNoSIEIENoPhoIso_idx'
            else :
                return None, None

    elif isinstance( iso_vals, tuple ) :
        # put a channel selection based on eleVeto when available
        if var == 'sigmaIEIE' :
            varstr = 'ph_noSIEIEiso%d%d%d_n' %(iso_vals)
            phstr = 'ptSorted_ph_noSIEIEiso%d%d%d_idx' %(iso_vals)
        elif var == 'chIsoCorr' :
            varstr = 'ph_passSIEIEisoNone%d%d_n' %(iso_vals[1], iso_vals[2])
            phstr = 'ptSorted_ph_passSIEIEisoNone%d%d_idx' %(iso_vals[1], iso_vals[2])
        elif var == 'neuIsoCorr' :
            varstr = 'ph_passSIEIEiso%dNone%d_n' %(iso_vals[0], iso_vals[2])
            phstr = 'ptSorted_ph_passSIEIEiso%dNone%d_idx' %(iso_vals[0], iso_vals[2])
        elif var == 'phoIsoCorr' :
            varstr = 'ph_passSIEIEiso%d%dNone_n' %(iso_vals[0], iso_vals[1])
            phstr = 'ptSorted_ph_passSIEIEiso%d%dNone_idx' %(iso_vals[0], iso_vals[1])
        else :
            return None, None
    else :
        return None, None

    return varstr, phstr

def get_real_template_draw_commands( var, ch='mu', eleVeto='NoEleVeto', iso_vals=None, dy=False ) :

    varstr, phstr = get_template_draw_strs( var, ch, eleVeto, iso_vals )

    #print '***********************************FIX DATA TEMPLATES************************************'

    if dy :
        return 'el_passtrig_n>0 && el_n==2 && %s == 1 && leadPhot_leadLepDR>0.4 && ph_truthMatch_el[%s[0]] ' %( varstr, phstr)
    else :
        #return 'mu_passtrig25_n>0 && mu_n==1 && %s == 1 && leadPhot_leadLepDR>0.4 && ph_truthMatch_ph[%s[0]] && abs(ph_truthMatchMotherPID_ph[%s[0]]) < 25 ' %( varstr, phstr, phstr )
        return 'mu_passtrig25_n>0 && mu_n==2 && %s == 1 && leadPhot_leadLepDR>0.4 && leadPhot_sublLepDR>0.4 && ph_truthMatch_ph[%s[0]] && abs(ph_truthMatchMotherPID_ph[%s[0]]) < 25 ' %( varstr, phstr, phstr )



def get_fake_template_draw_commands(var,  ch='mu', eleVeto='NoEleVeto', iso_vals=None ) :

    varstr, phstr = get_template_draw_strs( var, ch, eleVeto, iso_vals )

    return 'mu_passtrig25_n>0 && mu_n==2 && %s == 1 && fabs( m_leplep-91.2 ) < 5 && leadPhot_sublLepDR >1 && leadPhot_leadLepDR>1 ' %(varstr)

def get_corr_fake_template_draw_commands( ch='mu', fitvar='sigmaIEIE', r1='EB', r2='EB', leadPass=True, cuts='nom' ) :

    base_str = ''
    # in the muon channel remove the pixel seed veto
    if ch == 'mu' or ch=='muhighmt' or ch =='mulowmt' or ch =='muZgg' or ch == 'elZgg' :
        #base_str = '( (mu_passtrig25_n>0 && mu_n==1) || (el_passtrig_n>0 && el_n==1) ) && ph_HoverE12[0] < 0.05 && ph_HoverE12[1] < 0.05 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 %s ' %_mgg_cut
        base_str = 'mu_passtrig25_n>0  && dr_ph1_ph2 > 0.4 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 %s'%_mgg_cut
    #elif ch=='muZgg' :
    #    base_str = ' mu_n==2 && el_n==0 && dr_ph1_ph2 > 0.4 && dr_ph1_leadLep>0.4 && dr_ph2_leadLep>0.4 && dr_ph1_sublLep>0.4 && dr_ph2_sublLep>0.4 && m_leplep > 40 %s  '%_mgg_cut
    #elif ch=='elZgg' :
    #    base_str = ' mu_n==2 && el_n==0 && dr_ph1_ph2 > 0.4 && dr_ph1_leadLep>0.4 && dr_ph2_leadLep>0.4 && dr_ph1_sublLep>0.4 && dr_ph2_sublLep>0.4 && m_leplep > 40 %s '%_mgg_cut 
    else :
        #base_str = '( (mu_passtrig25_n>0 && mu_n==1) || (el_passtrig_n>0 && el_n==1) ) && ph_HoverE12[0] < 0.05 && ph_HoverE12[1] < 0.05 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 && hasPixSeed_leadph12 == 0 && hasPixSeed_sublph12 == 0  %s' %_mgg_cut

        if ch.count('invpixlead' ) :
            #base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 && hasPixSeed_leadph12 == 1 && hasPixSeed_sublph12 == 0 %s ' %_mgg_cut
            base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 %s ' %_mgg_cut
        elif ch.count('invpixsubl' ) :
            #base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 && hasPixSeed_leadph12 == 0 && hasPixSeed_sublph12 == 1 %s ' %_mgg_cut
            base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 %s ' %_mgg_cut
        else :
            #base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 && hasPixSeed_leadph12 == 0 && hasPixSeed_sublph12 == 0 %s ' %_mgg_cut
            base_str = 'mu_passtrig25_n>0 && mu_n==1 && el_n==0 && dr_ph1_leadLep > 0.4 && dr_ph2_leadLep > 0.4 && dr_ph1_ph2 > 0.4 %s ' %_mgg_cut

    if fitvar == 'sigmaIEIE' :
        if leadPass :
            var_cut = ' && sieie_leadph12 < %f ' %_sieie_cuts[r1][0]
        else :
            var_cut = ' && sieie_leadph12 > %f && sieie_leadph12 < %f ' %(_sieie_cuts[r1])
        if cuts == 'nom' :
            base_str += ' && ph_noSIEIEiso1299_n == 2 && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 12 && chIsoCorr_sublph12 < 12 && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < 9 && phoIsoCorr_sublph12 > %f && phoIsoCorr_sublph12 < 9 %s '%( _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'tight' :
            base_str += ' && ph_noSIEIEiso1077_n == 2 && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 10 && chIsoCorr_sublph12 < 10 && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < 7 && phoIsoCorr_sublph12 > %f && phoIsoCorr_sublph12 < 7 %s '%( _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'loose' :
            base_str += ' && ph_noSIEIEiso151111_n == 2 && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 15 && chIsoCorr_sublph12 < 15 && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < 11 && phoIsoCorr_sublph12 > %f && phoIsoCorr_sublph12 < 11 %s '%( _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'veryloose' :
            base_str += ' && ph_noSIEIEiso201616_n == 2 && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 20 && chIsoCorr_sublph12 < 20 && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < 16 && phoIsoCorr_sublph12 > %f && phoIsoCorr_sublph12 < 16 %s '%( _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )

    elif fitvar == 'chIsoCorr' :

        if leadPass :
            var_cut = ' && chIsoCorr_leadph12 < %f ' %_chIso_cuts[r1][0]
        else :
            var_cut = ' && chIsoCorr_leadph12 > %f && chIsoCorr_leadph12 < %f ' %(_chIso_cuts[r1])
        if cuts == 'nom' :
            base_str += ' && ph_failSIEIEisoNone55_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 5 && phoIsoCorr_sublph12 < 5 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'tight' :
            base_str += ' && ph_failSIEIEisoNone33_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 3 && phoIsoCorr_sublph12 < 3 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'loose' :
            base_str += ' && ph_failSIEIEisoNone77_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 7 && phoIsoCorr_sublph12 < 7 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'veryloose' :
            base_str += ' && ph_failSIEIEisoNone99_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 9 && phoIsoCorr_sublph12 < 9 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
    elif fitvar == 'phoIsoCorr' :
        if leadPass :
            var_cut = ' && phoIsoCorr_leadph12 < %f ' %_phoIso_cuts[r1][0]
        else :
            var_cut = ' && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < %f ' %(_phoIso_cuts[r1])
        if cuts == 'nom' :
            base_str += ' && ph_failSIEIEiso129None_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 12 && chIsoCorr_sublph12 < 12 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], var_cut )
        if cuts == 'tight' :
            base_str += ' && ph_failSIEIEiso107None_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 10 && chIsoCorr_sublph12 < 10   %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], var_cut )
        if cuts == 'loose' :
            base_str += ' && ph_failSIEIEiso1511None_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 15 && chIsoCorr_sublph12 < 15 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], var_cut )
        if cuts == 'veryloose' :
            base_str += ' && ph_failSIEIEiso2016None_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && ph_passNeuIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[1] && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 20 && chIsoCorr_sublph12 < 20 %s ' %( _sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], var_cut )
    elif fitvar == 'neuIsoCorr' :
        if leadPass :
            var_cut = ' && neuIsoCorr_leadph12 < %f ' %_neuIso_cuts[r1][0]
        else :
            var_cut = ' && neuIsoCorr_leadph12 > %f && neuIsoCorr_leadph12 < %f ' %(_neuIso_cuts[r1])
        if cuts == 'nom' :
            base_str += ' && ph_failSIEIEiso10None7_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 10 && chIsoCorr_sublph12 < 10 && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 7 && phoIsoCorr_sublph12 < 7   %s ' %(_sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'tight' :
            base_str += ' && ph_failSIEIEiso8None5_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 8 && chIsoCorr_sublph12 < 8 && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 5 && phoIsoCorr_sublph12 < 5     %s ' %(_sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'loose' :
            base_str += ' && ph_failSIEIEiso12None9_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 12 && chIsoCorr_sublph12 < 12 && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 9 && phoIsoCorr_sublph12 < 9   %s ' %(_sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )
        if cuts == 'veryloose' :
            base_str += ' && ph_failSIEIEiso15None11_n==2 && sieie_leadph12 > %f && sieie_sublph12 > %f && chIsoCorr_leadph12 > %f && chIsoCorr_sublph12 > %f && chIsoCorr_leadph12 < 15 && chIsoCorr_sublph12 < 15 && phoIsoCorr_leadph12 > %f && phoIsoCorr_sublph12 > %f && phoIsoCorr_leadph12 < 11 && phoIsoCorr_sublph12 < 11 %s ' %(_sieie_cuts[r1][0], _sieie_cuts[r2][0], _chIso_cuts[r1][0], _chIso_cuts[r2][0], _phoIso_cuts[r1][0], _phoIso_cuts[r2][0], var_cut )

    return base_str


def get_fake_window_template_draw_commands( ch='mu' ) :

    if ch == 'mu' or ch=='muhighmt' or ch =='mulowmt' :
        return 'mu_passtrig25_n>0 && mu_n==2 && ph_n==1 && ph_HoverE12[0] < 0.05 && fabs( m_leplep-91.2 ) < 5 && leadPhot_sublLepDR >1 && leadPhot_leadLepDR>1 && ph_chIsoCorr[0] > 2 && ph_chIsoCorr[0] < 10 && ph_passNeuIsoCorrMedium[0] && ph_passPhoIsoCorrMedium[0] ',
    else :
        return 'mu_passtrig25_n>0 && mu_n==2 && ph_n==1 && ph_HoverE12[0] < 0.05 && fabs( m_leplep-91.2 ) < 5 && leadPhot_sublLepDR >1 && leadPhot_leadLepDR>1 && ph_chIsoCorr[0] > 2 && ph_chIsoCorr[0] < 10 && ph_passNeuIsoCorrMedium[0] && ph_passPhoIsoCorrMedium[0] && ph_hasPixSeed[0]==0',

def get_default_draw_commands( ch='mu' ) :

    el_base = ' el_passtrig_n>0 && el_n==1 && mu_n==0 && dr_ph1_ph2 > 0.4 %s' %( _mgg_cut )
    el_base_inv = ' el_passtrig_n>0 && el_n>0 && mu_n==0 && dr_ph1_ph2 > 0.4 %s ' %( _mgg_cut )
    print '***************************FIX NARROW MASS WINDOW***************************'
    #zmass_window = 10
    zmass_window = 5

    # main Wgg commands
    draw_commands = {
        'mu' : ' mu_passtrig25_n>0 && el_n==0 && mu_n==1 && dr_ph1_ph2 > 0.4 %s '%_mgg_cut,
        'elzcr' : el_base + ' && (fabs(m_trigelphph-91.2) < %d) ' %zmass_window,
        'elzcrinvpixlead' : el_base_inv + ' && (fabs(m_trigelphph-91.2) < %d) ' %zmass_window,
        'elzcrinvpixsubl' : el_base_inv + ' && (fabs(m_trigelphph-91.2) < %d) ' %zmass_window,
        'elloose' : el_base,
        'ellooseinvpixlead' : el_base_inv ,
        'ellooseinvpixsubl' : el_base_inv,
        'elfull' : el_base + ' && !(fabs(m_trigelphph-91.2) < %d) && !(fabs(m_trigelph1-91.2) < %d)  && !(fabs(m_trigelph2-91.2) < %d)' %( zmass_window, zmass_window, zmass_window),
        'elfullinvpixlead' : el_base_inv + ' && !(fabs(m_trigelphph-91.2) < %d) && !(fabs(m_trigelph1-91.2) < %d)  && !(fabs(m_trigelph2-91.2) < %d)' %( zmass_window, zmass_window, zmass_window),
        'elfullinvpixsubl' : el_base_inv + ' && !(fabs(m_trigelphph-91.2) < %d) && !(fabs(m_trigelph1-91.2) < %d)  && !(fabs(m_trigelph2-91.2) < %d)' %( zmass_window, zmass_window, zmass_window),
        'elph1zcr' : el_base + ' &&  (fabs(m_trigelph1-91.2) < %d) ' %zmass_window,
        'elph1zcrinvpixlead' : el_base_inv + ' &&  (fabs(m_trigelph1-91.2) < %d) ' %zmass_window,
        'elph1zcrinvpixsubl' : el_base_inv + ' &&  (fabs(m_trigelph1-91.2) < %d) ' %zmass_window,
        'elph2zcr' : el_base + ' &&  (fabs(m_trigelph2-91.2) < %d) ' %zmass_window,
        'elph2zcr_invpixlead' : el_base + ' &&  (fabs(m_trigelph2-91.2) < %d) ' %zmass_window,
        'elph2zcr_invpixsubl' : el_base + ' &&  (fabs(m_trigelph2-91.2) < %d) ' %zmass_window,
    }
    # add low/high mT selections
    draw_keys = draw_commands.keys()
    for key in draw_keys :
        val = draw_commands[key]
        if key.count( 'el' ) :
            draw_commands[key+'lowmt']  = val + ' && mt_trigel_met < 40 '
            draw_commands[key+'highmt'] = val + ' && mt_trigel_met > 40 '
        else :
            draw_commands[key+'lowmt']  = val + ' && mt_trigmu_met < 40 '
            draw_commands[key+'highmt'] = val + ' && mt_trigmu_met > 40 '

    ## add inverted selections
    ## should be the same as non-inverted 
    ## cases
    #draw_keys = draw_commands.keys()
    #for key in draw_keys :
    #    val = draw_commands[key]
    #    draw_commands[key+'invpixlead'] = val 
    #    draw_commands[key+'invpixsubl'] = val 
   

    # add Zgg selections
    draw_commands['muZgg'] = '(passTrig_mu17_mu8 || passTrig_mu17_Tkmu8) && mu_n==2 && dr_ph1_ph2 > 0.4  && dr_ph1_leadLep>0.4 && dr_ph2_leadLep>0.4 && dr_ph1_sublLep>0.4 && dr_ph2_sublLep>0.4 && m_mumu > 40 %s  '%_mgg_cut
    draw_commands['elZgg'] = 'passTrig_ele17_ele8_9  &&  el_n==2 && dr_ph1_ph2 > 0.4 && dr_ph1_leadLep>0.4 && dr_ph2_leadLep>0.4 && dr_ph1_sublLep>0.4 && dr_ph2_sublLep>0.4  && m_elel > 40 %s '%_mgg_cut

    return draw_commands.get( ch, None )

def get_default_samples(ch='mu' ) :

    print '************************************FIX USING ZGAMMA******************************************'
    if ch.count('mu')  :
        #return { 'real' : {'Data' : 'Wgamma'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Muon' }
        return { 'real' : {'Data' : 'Zgamma'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Muon' }
        #return { 'real' : {'Data' : 'Muon'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Muon' }
        #return { 'real' : {'Data' : 'Muon'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Muon' }
    elif ch.count('el') :
        if ch.count('invpix') :
            return { 'real' : {'Data' : 'DYJetsToLL'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Electron' }
        else :
            #return { 'real' : {'Data' : 'Wgamma'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Electron' }
            return { 'real' : {'Data' : 'Zgamma'}, 'fake' : {'Data' : 'Muon', 'Background' : 'RealPhotonsZg'}, 'target' : 'Electron' }


    #print '*************************************USING MC SAMPLES***************************'
    #if ch.count('mu') :
    #    return { 'real' : {'Data' : 'Wgamma'}, 'fake' : {'Data' : 'ZjetsZgamma'}, 'target' : 'WZall' }
    #elif ch.count('el') :
    #    return { 'real' : {'Data' : 'Wgamma'}, 'fake' : {'Data' : 'ZjetsZgamma'}, 'target' : 'WZall' }


def get_default_cuts(var='sigmaIEIE') :

    if var == 'sigmaIEIE' :

        return { 'EB' : { 'tight' : ( 0, _sieie_cuts['EB'][0]-0.0001  ), 'loose' : ( _sieie_cuts['EB'][0]+0.0001,_sieie_cuts['EB'][1]-0.0001  ) },
                 'EE' : { 'tight' : ( 0, _sieie_cuts['EE'][0]-0.0001 ), 'loose' : (  _sieie_cuts['EE'][0]+0.0001,_sieie_cuts['EE'][1]-0.0001  ) } 
               }
    elif var == 'chIsoCorr' :
        #return { 'EB' : { 'tight' : ( 0, 1.5-0.01  ), 'loose' : ( 1.5001, 45 ) },
        #         'EE' : { 'tight' : ( 0, 1.2-0.01 ), 'loose' : ( 1.2001, 42 ) } 
        #       }
        return { 'EB' : { 'tight' : ( 0, _chIso_cuts['EB'][0]-0.01  ), 'loose' : ( _chIso_cuts['EB'][0] + 0.01, _chIso_cuts['EB'][1]-0.01 ) },
                 'EE' : { 'tight' : ( 0, _chIso_cuts['EE'][0]-0.01 ) , 'loose' : ( _chIso_cuts['EE'][0] + 0.01, _chIso_cuts['EE'][1]-0.01 ) } 
               }
    elif var == 'neuIsoCorr' :
        #return { 'EB' : { 'tight' : ( -2, 1.0-0.01  ), 'loose' : ( 1.0001, 40 ) },
        #         'EE' : { 'tight' : ( -2, 1.5-0.01 ), 'loose' : ( 1.5001, 45 ) } 
        #       }
        return { 'EB' : { 'tight' : ( -2, _neuIso_cuts['EB'][0]-0.01  ), 'loose' : ( _neuIso_cuts['EB'][0]+0.01, _neuIso_cuts['EB'][1]-0.01 ) },
                 'EE' : { 'tight' : ( -2, _neuIso_cuts['EE'][0]-0.01 ) , 'loose' : ( _neuIso_cuts['EE'][0]+0.01, _neuIso_cuts['EE'][1]-0.01 ) } 
               }
    elif var == 'phoIsoCorr' :
        #return { 'EB' : { 'tight' : ( -2.1, 0.7-0.001  ), 'loose' : ( 0.70001, 35 ) },
        #         'EE' : { 'tight' : ( -2, 1.0-0.001 ), 'loose' : ( 1.0001, 50 ) } 
        #       }
        return { 'EB' : { 'tight' : ( -2.1, _phoIso_cuts['EB'][0]-0.01  ), 'loose' : ( _phoIso_cuts['EB'][0]+0.01, _phoIso_cuts['EB'][1]-0.01 ) },
                 'EE' : { 'tight' : ( -2, _phoIso_cuts['EE'][0]-0.01 )   , 'loose' : ( _phoIso_cuts['EE'][0]+0.01, _phoIso_cuts['EE'][1]-0.01 ) } 
               }

syst_uncertainties={}
def get_syst_uncertainty(var, type, reg, ptrange, real_fake, tight_loose ) :

    # Put these in by hand, may be necessary to load later
    if type.count( 'Background' ) :
        #use a flat 20% uncertainty for now
        return 0.20

    if not syst_uncertainties :
        print 'Systematics not loaded!  Use --syst_file to provide systematics file'
        return 0.0

    var_data = syst_uncertainties.get( var, None )
    if var_data is None :
        print 'no systematics available for %s' %var
        raw_input('con')
        return 0.0

    type_data = var_data.get( type, None )
    if type_data is None :
        print 'no systematics available for %s, %s' %(var, type)
        raw_input('con')
        return 0.0

    reg_data = type_data.get( reg, None )

    if reg_data is None :
        print 'No systematics available for region %s for type %s' %(reg, type)
        raw_input('con')
        return 0.0

    syst_ptrange = ( str(ptrange[0]), str(ptrange[1]) )
    if ptrange[0] is None :
        syst_ptrange = (None,None)
    elif ptrange[1] is None :
        syst_ptrange = (str(ptrange[0]), 'max')

    pt_data = reg_data.get(syst_ptrange, None)
    if pt_data is None :
        print 'No systematics available for pt range %s, region %s, type %s' %(syst_ptrange, reg, type)
        raw_input('con')
        return 0.0

    return reg_data[syst_ptrange]


             
def main() :

    global sampManLLG
    global sampManLG
    global sampManData
    global sampManDataNOEV
    global sampManDataFF
    global sampManDataInvL
    global sampManDataInvS
    global sampManInvReal

    #base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDVetoPixSeedBoth_2015_10_01'
    #base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhID_2015_10_01'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedLead_2015_10_01'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedSubl_2015_10_01'

    base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDVetoPixSeedBoth_2015_11_11'
    base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhID_2015_11_09'
    base_dir_data_ff      = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhID_2015_11_09'
    base_dir_inv_real     = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaNoPhIDNoTrigOlapRm_2016_05_30'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedLead_2015_11_11'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedSubl_2015_11_11'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoElOlapRmInvPSVLead_2016_02_04'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoElOlapRmInvPSVSubl_2016_02_04'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoElOlapRm_2016_02_05'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoElOlapRm_2016_02_05'
    base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoTrigElOlapRmDupInvPSVLead_2016_03_05'
    base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoTrigElOlapRmDupInvPSVSubl_2016_03_05'

    #base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDVetoCSEVSeedBoth_2015_11_11'
    #base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhID_2015_11_09'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvCSEVLead_2015_11_11'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvCSEVSubl_2015_11_11'

    #base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleOlapRMVetoCSEVSeedBoth_2015_11_30'
    #base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleOlapRM_2015_11_30'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleOlapRMInvCSEVLead_2015_11_30'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleOlapRMInvCSEVSubl_2015_11_30'

    if options.zgg :
        base_dir_data_ff      = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhID_2015_11_09'
        #base_dir_data_ff      = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaGammaNoPhID_2015_11_09'
        base_dir_data         = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaGammaNoPhID_2015_11_09'
        base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaGammaNoPhID_2015_11_09'
        base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaGammaNoPhID_2015_11_09'
        base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaGammaNoPhID_2015_11_09'

    #base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDWithEleOlapVetoPixSeedBoth_2015_09_03'
    #base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDWithEleOlap_2015_09_03'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDWithEleOlapInvPixSeedLead_2015_09_03'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDWithEleOlapInvPixSeedSubl_2015_09_03'

    #base_dir_data         = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleVetoVetoPixSeedBoth_2015_08_31'
    #base_dir_data_noeveto = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleVeto_2015_08_31'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleVetoInvPixSeedLead_2015_08_31'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/private/CMS/Wgamgam/Output/LepGammaGammaNoPhIDNoEleVetoInvPixSeedSubl_2015_08_31'
    #base_dir_data_invl    = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedLead_2015_08_01'
    #base_dir_data_invs    = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaGammaNoPhIDInvPixSeedSubl_2015_08_01'
    base_dir_llg = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepLepGammaNoPhID_2015_11_09'
    base_dir_lg = '/afs/cern.ch/work/j/jkunkle/public/CMS/Wgamgam/Output/LepGammaNoPhID_2015_11_09'

    sampManLLG      = SampleManager(base_dir_llg, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManLG       = SampleManager(base_dir_lg, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManData     = SampleManager(base_dir_data, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManDataNOEV = SampleManager(base_dir_data_noeveto, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManDataFF   = SampleManager(base_dir_data_ff, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManDataInvL = SampleManager(base_dir_data_invl, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManDataInvS = SampleManager(base_dir_data_invs, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)
    sampManInvReal  = SampleManager(base_dir_inv_real, options.treeName,filename=options.fileName, xsFile=options.xsFile, lumi=options.lumi, quiet=options.quiet)

    if options.samplesConf is not None :

        sampManLLG.ReadSamples( options.samplesConf )
        sampManLG.ReadSamples( options.samplesConf )

        if options.samplesConfWgg is None  :
            options.samplesConfWgg = options.samplesConfGG
        

        sampManDataNOEV.ReadSamples( options.samplesConfGG )
        #sampManDataFF.ReadSamples( options.samplesConfGG )
        sampManDataFF.ReadSamples( options.samplesConfWgg )
        sampManData.ReadSamples( options.samplesConfGG )
        sampManDataInvL.ReadSamples( options.samplesConfGG )
        sampManDataInvS.ReadSamples( options.samplesConfGG )
        sampManInvReal.ReadSamples( options.samplesConfGG )

    if options.outputDir is not None :
        if not os.path.isdir( options.outputDir ) :
            os.makedirs( options.outputDir )

    #RunClosureFitting( outputDir = None )

    if options.syst_file is not None :
        load_syst_file( options.syst_file )

    all_samp_man = []
    all_samp_man.append( sampManLG)
    all_samp_man.append( sampManLLG)
    all_samp_man.append( sampManData)
    all_samp_man.append( sampManDataNOEV)
    all_samp_man.append( sampManDataFF )
    all_samp_man.append( sampManDataInvL)
    all_samp_man.append( sampManDataInvS)
    all_samp_man.append( sampManInvReal)

    for s in all_samp_man  :
        s.deactivate_all_samples()

    #channels = ['muhighmt']
    #channels = ['mulowmt']
    channels=['mu']
    #channels = ['muZgg', 'elZgg']
    #channels = ['muZgg']
    #channels = ['elZgg']
    #channels = ['ellooselowmt']
    #channels = ['ellooselowmtinvpixlead']
    #channels = ['ellooselowmtinvpixsubl']

    #channels = ['elfullhighmt']
    #channels = ['elfullhighmtinvpixlead']
    #channels = ['elfullhighmtinvpixsubl']

    #channels = ['elfulllowmt']
    #channels = ['elfulllowmtinvpixlead']
    #channels = ['elfulllowmtinvpixsubl']

    #channels = ['elzcrhighmt']
    #channels = ['elzcrhighmtinvpixlead']
    #channels = ['elzcrhighmtinvpixsubl']

    #channels = ['elzcr']
    #channels = ['elzcrinvpixlead']
    #channels = ['elzcrinvpixsubl']

    calculators = []

    if options.channels is not None :
        channels = options.channels.split(',')

    fftypes = ['nom', 'veryloose', 'loose', 'tight', 'None']

    fitvar_corrs = { 
                     'chIsoCorr' : ['No SIEIE'], 
                     #'sigmaIEIE' : [(5,3,3) , (8,5,5), (10,7,7)]
                   }

    #eleVeto = 'PassCSEV'
    eleVeto = 'PassPSV'

    pt_bins = common_ptbins

    if options.sublptbins is not None :
        split = options.sublptbins.split(',')
        if split[1] == 'None' :
            subl_ptrange = (int(split[0]), None )
        else :
            subl_ptrange = (int(split[0]), int(split[1]) )
    else :
        subl_ptrange = ( common_ptbins[0], None )

    
    kinevars_common = {
                       #'m_ph1_ph2'    : [(0, 30), (30, 60), (60, 90), (90, 120), (120, 150), (150, 180), ( 180, 210), (210, 240), (240, 1000000)], 
                       'm_ph1_ph2'    : [(0, 60), (60, 120), (120, 240), (240, 1000000)], 
                       'pt_ph1_ph2'   : [(0,20), (20,40), (40,60), (60,80), (80,1000000)],
                      }


    #kinevars_ele = { 'mt_trigel_met'  : [(40, 60), (60, 80), (80, 120), (120,1000000)] }
    #kinevars_mu  = { 'mt_trigmu_met'  : [(40, 60), (60, 80), (80, 120), (120,1000000)] }
    kinevars_ele = {  }
    kinevars_mu  = { }

    if options.zgg :
        kinevars_ele = {'m_elel'   : [(40,60), (60,80), (80, 100), (100, 1000000)] }
        kinevars_mu = {'m_mumu'   : [(40,60), (60,80), (80, 100), (100, 1000000)] }
        kinevars_common = {
                           'm_ph1_ph2'    : [(0, 20), (20, 40), (40, 60), (60, 100), (100,160), (160, 1000000)], 
                           'pt_ph1_ph2'   : [(0,20), (20,40), (40,60), (60,80), (80,1000000)],
                           'm_leplepphph' : [(80,100), (100,150), (150,200), (200,250), (250,300), (300,1000000)],
                          }

    # if using mutliple pT bins, don't bin in other variables
    if len(pt_bins) > 2 :
        kinevars_common = {}
        kinevars_ele    = {}
        kinevars_mu     = {}

    #for ch in channels :
    #    for var in fitvar_corrs.keys() :
    #        for ffcorr in fftypes :

    #            #calculators.append( RunNominalCalculation(fitvar=var, channel=ch, ffcorr=ffcorr, eleVeto=eleVeto, outputDir=options.outputDir+str(ptbins[0])+'/JetFakeResultsSyst', ptbins=ptbins) )
    #            calculators.append( RunNominalCalculation(fitvar=var, channel=ch, ffcorr=ffcorr, ptbins=pt_bins, subl_ptrange=subl_ptrange, eleVeto=eleVeto, outputDir=options.outputDir+'/JetFakeResultsSyst') )

    for var, corr_vals in fitvar_corrs.iteritems() :
        for cv in corr_vals :
            for ch in channels :
                for ffcorr in fftypes :
                    kinevars = dict( kinevars_common )
                    #add channel dependent kinematic vars
                    if ch.count( 'mu')  :
                        kinevars.update( kinevars_mu )
                    if ch.count( 'el') :
                        kinevars.update( kinevars_ele )
                    calculators.append( RunCorrectedAsymCalculation(fitvar=var, channel=ch, ffcorr=ffcorr, vals=cv, ptbins=pt_bins, subl_ptrange=subl_ptrange, eleVeto=eleVeto, addtlVar=None, addtlVarCut=None, outputDir=options.outputDir+'/JetFakeResultsSyst') )
                    for kinevar, cuts in kinevars.iteritems() :
                        for cut in cuts :
                            #calculators.append( RunCorrectedAsymCalculation(fitvar=var, channel=ch, ffcorr=ffcorr, vals=cv, eleVeto=eleVeto, outputDir=options.outputDir+str(ptbins[0])+'/JetFakeResultsSyst', ptbins=ptbins) )
                            calculators.append( RunCorrectedAsymCalculation(fitvar=var, channel=ch, ffcorr=ffcorr, vals=cv, ptbins=pt_bins, subl_ptrange=subl_ptrange, eleVeto=eleVeto, addtlVar=kinevar, addtlVarCut=cut, outputDir=options.outputDir+'/JetFakeResultsSyst') )

    for calc in calculators :
        draw_configs = calc.ConfigHists()

    for s in all_samp_man  :
        s.run_commands()

    for calc in calculators :
        calc.execute()

    print 'Ran channel %s' %ch
    print '^_^ FINISHED ^_^'

def load_syst_file( file ) :

    global syst_uncertainties

    if os.path.isfile( file ) :
        ofile = open( file ) 
        syst_uncertainties = pickle.load(ofile)

        ofile.close()
    else :
        print 'WARNING -- Systematics file, %s, was not found!' %file

#Depricated -- use classes
#def RunNomFitting( outputDir = None, ch='mu', ffcorr='None') :
#
#    outputDirNom = None
#    if outputDir is not None :
#        if options.fitvar == 'sigmaIEIE' :
#            outputDirNom = outputDir + '/SigmaIEIEFits/JetFakeTemplateFitPlotsNomIso'
#        elif options.fitvar == 'chIsoCorr' :
#            outputDirNom = outputDir + '/ChHadIsoFits/JetFakeTemplateFitPlotsNomIso'
#        elif options.fitvar == 'neuIsoCorr' :
#            outputDirNom = outputDir + '/NeuHadIsoFits/JetFakeTemplateFitPlotsNomIso'
#        elif options.fitvar == 'phoIsoCorr' :
#            outputDirNom = outputDir + '/PhoIsoFits/JetFakeTemplateFitPlotsNomIso'
#
#    do_nominal_fit( ptbins=common_ptbins, fitvar=options.fitvar, ch=ch, ffcorr=ffcorr, outputDir = outputDirNom, systematics='Nom')
#
#    # use last leading pt bin
#    #subl_pt_lead_bins = [ common_ptbins[-2],  common_ptbins[-1] ]
#    #do_nominal_fit( iso_cuts_lead, iso_cuts_subl, ptbins=[40, 1000000], subl_ptrange=(40, 1000000), fitvar=var, ch=ch, outputDir = outputDirNom, systematics='Nom')
#    #do_nominal_fit( iso_cuts_lead, iso_cuts_subl, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[1], None), ch=ch, outputDir = outputDirNom, systematics='Nom')
#
#    #do_nominal_fit( iso_cuts_lead, iso_cuts_subl, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[0], common_ptbins[2]), ch=ch, outputDir = outputDirNom, systematics='Nom')
#    #do_nominal_fit( iso_cuts_lead, iso_cuts_subl, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[2], None), ch=ch, outputDir = outputDirNom, systematics='Nom')

def RunClosureFitting( outputDir = None, ch='mu' ) :

    outputDirNom = None
    if outputDir is not None :
        outputDirNom = outputDir + '/JetFakeTemplateClosureNomIso'

    iso_cuts_lead = 'ph_passChIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[0] && ph_passPhoIsoCorrMedium[0] '
    iso_cuts_subl = 'ph_passChIsoCorrMedium[1] && ph_passNeuIsoCorrMedium[1] && ph_passPhoIsoCorrMedium[1] '
    do_closure_fit( iso_cuts_lead, iso_cuts_subl, ptbins=common_ptbins, ch=ch, corr_factor=-0.05, outputDir = outputDirNom )

# depricated, use classes
#def RunLooseFitting( outputDir = None, ch='mu' ) :
#
#    outputDirNom = None
#    if outputDir is not None :
#        outputDirNom = outputDir + '/JetFakeTemplateFitPlotsLooseIso'
#
#    iso_cuts_lead = ' ph_chIsoCorr[0] < 5 && ph_neuIsoCorr[0] < 3 && ph_phoIsoCorr[0] < 3'
#    iso_cuts_subl = ' ph_chIsoCorr[1] < 5 && ph_neuIsoCorr[1] < 3 && ph_phoIsoCorr[1] < 3'
#
#    do_nominal_fit( so_cuts_lead, iso_cuts_subl, ptbins=common_ptbins, ch=ch, outputDir = outputDirNom )

def RunAsymFittingLoose(vals, outputDir = None, ch='mu') :

    outputDirNom = None
    if outputDir is not None :
        outputDirNom = outputDir + '/JetFakeTemplateFitPlotsLoose%d-%d-%dAsymIso'%(vals[0], vals[1], vals[2] )

    iso_cuts_iso = ' ph_passChIsoCorrMedium[0] && ph_passNeuIsoCorrMedium[0] && ph_passPhoIsoCorrMedium[0] '
    iso_cuts_noiso = ' ph_chIsoCorr[0] < %d && ph_neuIsoCorr[0] < %d && ph_phoIsoCorr[0] < %d' %(vals[0], vals[1], vals[2] )

    do_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, ptbins=common_ptbins, ch=ch, outputDir=outputDirNom )

# depricated, use classes
#def RunCorrectedAsymFitting(vals, outputDir = None, ch='mu', ffcorr='None') :
#
#
#    # make the output dir based on the iso vals
#    outputDirNom = None
#    if outputDir is not None :
#        if options.fitvar == 'sigmaIEIE' :
#            outputDirNom = outputDir + '/SigmaIEIEFits/JetFakeTemplateFitPlotsCorr%d-%d-%dAsymIso'%(vals[0], vals[1], vals[2] )
#        elif options.fitvar == 'chIsoCorr' :
#            outputDirNom = outputDir + '/ChHadIsoFits/JetFakeTemplateFitPlotsCorr%d-%d-%dAsymIso'%(vals[0], vals[1], vals[2] )
#        elif options.fitvar == 'neuIsoCorr' :
#            outputDirNom = outputDir + '/NeuHadIsoFits/JetFakeTemplateFitPlotsCorr%d-%d-%dAsymIso'%(vals[0], vals[1], vals[2] )
#        elif options.fitvar == 'phoIsoCorr' :
#            outputDirNom = outputDir + '/PhoIsoFits/JetFakeTemplateFitPlotsCorr%d-%d-%dAsymIso'%(vals[0], vals[1], vals[2] )
#
#    if options.fitvar == 'sigmaIEIE' :
#        #---------------------------------------------------
#        # for using SIEIE templates
#        # iso cuts for isolated photons
#        fitvar = 'sigmaIEIE'
#        # loosened iso cuts
#        loose_iso_cuts = vals
#        systematics=('-'.join([str(v) for v in vals]))
#        #---------------------------------------------------
#
#    elif options.fitvar == 'chIsoCorr' :
#        #---------------------------------------------------
#        # for using ChHadIso templates
#        # iso cuts for isolated photons
#        fitvar = 'chIsoCorr'
#        loose_iso_cuts = (None, vals[1], vals[2] )
#        systematics = 'No Cut-%d-%d' %( vals[1], vals[2] )
#        #---------------------------------------------------
#
#    elif options.fitvar == 'neuIsoCorr' :
#        #---------------------------------------------------
#        # for using NeuHadIso templates
#        # iso cuts for isolated photons
#        fitvar = 'neuIsoCorr'
#        # loosened iso cuts
#        loose_iso_cuts = (vals[0], None, vals[2] )
#        systematics = '%d-No Cut-%d' %( vals[0], vals[2] )
#        #---------------------------------------------------
#
#    elif options.fitvar == 'phoIsoCorr' :
#        #---------------------------------------------------
#        # for using NeuHadIso templates
#        # iso cuts for isolated photons
#        fitvar = 'phoIsoCorr'
#        # loosened iso cuts
#        loose_iso_cuts = (vals[0], vals[1], None )
#        systematics = '%d-%d-No Cut' %( vals[0], vals[1] )
#        #---------------------------------------------------
#
#    do_corrected_asymiso_fit(  loose_iso_cuts, ptbins=common_ptbins, fitvar=fitvar, ch=ch, ffcorr=ffcorr, outputDir=outputDirNom, systematics=systematics )
#
#    # ----------------------------
#    # subleading binning
#    # Uncomment to use sublead binning
#    # in specific lead pt bins
#    # ----------------------------
#    #subl_pt_lead_bins = [ common_ptbins[-2],  common_ptbins[-1] ]
#    #do_corrected_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, loose_iso_cuts, ptbins=[40,1000000], subl_ptrange=(40, None), fitvar=fitvar, ch=ch, outputDir = outputDirNom, systematics='Nom')
#    #do_corrected_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[0], common_ptbins[1]), ch=ch, outputDir = outputDirNom, systematics='Nom')
#    #do_corrected_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[1], None), ch=ch, outputDir = outputDirNom, systematics='Nom')
#
#    #do_corrected_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[0], common_ptbins[2]), ch=ch, outputDir = outputDirNom, systematics='Nom')
#    #do_corrected_asymiso_fit( iso_cuts_iso, iso_cuts_noiso, ptbins=subl_pt_lead_bins, subl_ptrange=(common_ptbins[2], None), ch=ch, outputDir = outputDirNom, systematics='Nom')
#    # ----------------------------

# depricated, use classes
#def do_nominal_fit( iso_cuts_lead=None, iso_cuts_subl=None, ptbins=[], subl_ptrange=(None,None), fitvar='sigmaIEIE', ch='mu', ffcorr='None', outputDir=None, systematics=None ) :
#
#    binning = get_default_binning(fitvar)
#    samples = get_default_samples(ch)
#
#    # generate templates for both EB and EE
#    real_template_str = get_real_template_draw_commands(fitvar, ch ) 
#    if iso_cuts_lead :
#        real_template_str += ' && ' + iso_cuts_lead
#
#    fake_template_str = get_fake_template_draw_commands(fitvar, ch ) 
#    if iso_cuts_lead :
#        fake_template_str += ' && ' + iso_cuts_lead
#
#    #if fitvar == 'sigmaIEIE' :
#    #    #print '*******************************DRAWING WITH CHHadISO WINDOW*******************************'
#    #    #fake_template_str = get_fake_window_template_draw_commands(ch )
#    #else :
#    #    fake_template_str = get_fake_template_draw_commands(fitvar,ch ) + ' && %s' %iso_cuts_lead
#
#    templates_reg = {}
#    templates_reg['EB'] = {}
#    templates_reg['EE'] = {}
#    templates_reg['EB']['real'] = get_single_photon_template(real_template_str, binning['EB'], samples['real'], 'EB', fitvar=fitvar, sampMan=sampManLG)
#    templates_reg['EE']['real'] = get_single_photon_template(real_template_str, binning['EE'], samples['real'], 'EE', fitvar=fitvar, sampMan=sampManLG)
#    templates_reg['EB']['fake'] = get_single_photon_template(fake_template_str, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, sampMan=sampManLLG)
#    templates_reg['EE']['fake'] = get_single_photon_template(fake_template_str, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, sampMan=sampManLLG)
#
#    templates_corr = None
#    if ffcorr != 'None' :
#        corr_template_str_leadFail_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=True , cuts=ffcorr )
#        corr_template_str_leadFail_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=True , cuts=ffcorr )
#        corr_template_str_leadFail_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=True , cuts=ffcorr )
#
#        templates_corr = {'leadPass' : {}, 'leadFail' : {}}
#
#        templates_corr['leadFail'][('EB','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EB','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadFail'][('EB','EE')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EB','EE')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadFail'][('EE','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EE','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#
#    regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB')]
#    for reg in regions :
#
#        # convert from regions to lead/subl
#        templates = {}
#        templates['lead'] = {}
#        templates['subl'] = {}
#        templates['lead']['real'] = templates_reg[reg[0]]['real']
#        templates['subl']['real'] = templates_reg[reg[1]]['real']
#        templates['lead']['fake'] = templates_reg[reg[0]]['fake']
#        templates['subl']['fake'] = templates_reg[reg[1]]['fake']
#
#        count_var, phstr = get_template_draw_strs( fitvar, ch, eleVeto )
#        count_var = None
#        if fitvar == 'sigmaIEIE' :
#            # if the channel inverts one of the pixel seeds then don't require the veto
#            # if its the muon channel don't require the veto
#            if ch.count('invpix') or ch == 'mu' or ch=='mulowmt' or ch=='muhighmt' :
#                count_var = 'ph_mediumNoSIEIENoEleVeto_n'
#            else :
#                count_var = 'ph_mediumNoSIEIE_n'
#        if fitvar == 'chIsoCorr' :
#            count_var = 'ph_mediumNoChIso_n'
#        if fitvar == 'neuIsoCorr' :
#            count_var = 'ph_mediumNoNeuIso_n'
#        if fitvar == 'phoIsoCorr' :
#            count_var = 'ph_mediumNoPhoIso_n'
#
#
#        #print '*******************FIX COUNT VAR*********************'
#        #count_var = 'ph_iso533_n'
#
#        # add regions onto the selection
#
#        if fitvar == 'sigmaIEIE' :
#            gg_selection = get_default_draw_commands(ch) + ' && %s >1 &&  is%s_leadph12 && is%s_sublph12 ' %( count_var, reg[0], reg[1] )
#        elif fitvar == 'chIsoCorr' :
#            gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passNeuIsoCorrMedium[0]==1 && ph_passPhoIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passNeuIsoCorrMedium[1]==1 && ph_passPhoIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#        elif fitvar == 'neuIsoCorr' :
#            gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passChIsoCorrMedium[0]==1 && ph_passPhoIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passChIsoCorrMedium[1]==1 && ph_passPhoIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#        elif fitvar == 'phoIsoCorr' :
#            gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passChIsoCorrMedium[0]==1 && ph_passNeuIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passChIsoCorrMedium[1]==1 && ph_passNeuIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#
#        #gg_selection = get_default_draw_commands(ch) + ' && %s >1 &&  is%s_leadph12 && is%s_sublph12 ' %( count_var, reg[0], reg[1] )
#
#        #gg_selection = get_default_draw_commands(ch) + ' && ph_iso151111_n > 1 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1])
#        #gg_selection = get_default_draw_commands(ch) + ' && ph_iso533_n > 1 && is%s_leadph12 && is%s_sublph12 && chIsoCorr_leadph12 < 3 && neuIsoCorr_leadph12 < 2 && phoIsoCorr_leadph12 < 2 && chIsoCorr_sublph12 < 3 && neuIsoCorr_sublph12 < 2 && phoIsoCorr_sublph12 < 2  ' %( reg[0], reg[1])
#        #gg_selection = get_default_draw_commands(ch) + ' && ph_iso533_n > 1 && chIsoCorr_leadph12 < 3 && neuIsoCorr_leadph12 < 2 && phoIsoCorr_leadph12 < 2 && chIsoCorr_sublph12 < 3 && neuIsoCorr_sublph12 < 2 && phoIsoCorr_sublph12 < 2 && ( ( ph_pt[0] > ph_pt[1] && is%s_leadph12 && is%s_sublph12 ) || ( ph_pt[0] <= ph_pt[1] && is%s_sublph12 && is%s_leadph12) ) ' %( reg[0], reg[1], reg[0], reg[1])
#
#        # add subl pt cuts onto the selection
#        if subl_ptrange[0] is not None :
#            if subl_ptrange[1] is None :
#                gg_selection = gg_selection + ' && pt_sublph12 > %d' %subl_ptrange[0]
#            else :
#                gg_selection = gg_selection + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(subl_ptrange[0], subl_ptrange[1] )
#
#        # parse out the x and y binning
#        ybinn = binning[reg[1]]
#        xbinn = binning[reg[0]]
#
#        # variable given to TTree.Draw
#        if fitvar == 'sigmaIEIE' :
#            var = 'pt_leadph12:sieie_sublph12:sieie_leadph12' #z:y:x
#        elif fitvar == 'chIsoCorr' :
#            var = 'pt_leadph12:chIsoCorr_sublph12:chIsoCorr_leadph12' #z:y:x
#        elif fitvar == 'neuIsoCorr' :
#            var = 'pt_leadph12:neuIsoCorr_sublph12:neuIsoCorr_leadph12' #z:y:x
#        elif fitvar == 'phoIsoCorr' :
#            var = 'pt_leadph12:phoIsoCorr_sublph12:phoIsoCorr_leadph12' #z:y:x
#
#        print 'USE var ', var
#        # get sample
#        if ch.count('invpixlead' ) :
#            print 'USE sampManDataInvL'
#            target_samp = sampManDataInvL.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw Data                       '
#            print gg_selection
#            print '---------------------------------'
#            gg_hist = clone_sample_and_draw( target_samp[0], var, gg_selection, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=sampManDataInvL )
#        elif ch.count('invpixsubl' ) :
#            print 'USE sampManDataInvS'
#            target_samp = sampManDataInvS.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw Data                       '
#            print gg_selection
#            print '---------------------------------'
#            gg_hist = clone_sample_and_draw( target_samp[0], var, gg_selection, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=sampManDataInvS )
#
#        # in the muon channel don't make the electron veto cut
#        elif ch.count( 'mu' ) :
#            print 'USE sampManDataNOEV'
#            target_samp = sampManDataNOEV.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw Data                       '
#            print gg_selection
#            print '---------------------------------'
#            gg_hist = clone_sample_and_draw( target_samp[0], var, gg_selection, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=sampManDataNOEV )
#        else :
#            print 'USE sampManData'
#            target_samp = sampManData.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw Data                       '
#            print gg_selection
#            print '---------------------------------'
#            gg_hist = clone_sample_and_draw( target_samp[0], var, gg_selection, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=sampManData )
#
#
#        run_nominal_calculation( gg_hist, templates, templates_corr, reg, ptbins, ch, fitvar, ffcorr, systematics, subl_ptrange, outputDir )

def run_nominal_calculation( gg_hist, templates, templates_corr, reg, ptbins, ch, fitvar, ffcorr, systematics=None, subl_ptrange=(None,None), outputDir=None ) :

    # -----------------------
    # inclusive result
    # -----------------------

    # project data hist
    if isinstance( gg_hist, dict ) and 'leadPass' in gg_hist :
        gg_hist_inclusive = {}
        gg_hist_inclusive['leadPass'] = gg_hist['leadPass'].ProjectionX( 'gg_hist_px_lead_pass' )
        gg_hist_inclusive['leadFail'] = gg_hist['leadFail'].ProjectionX( 'gg_hist_px_lead_fail' )
        print 'Integral gg_hist_inclusive, leadPass ', gg_hist_inclusive['leadPass'].Integral()
        print 'Integral gg_hist_inclusive, leadFail ', gg_hist_inclusive['leadFail'].Integral()
    else :
        gg_hist_inclusive = gg_hist.Project3D( 'yx' )
        print 'Ingegral gg_hist_inclusive ', gg_hist_inclusive.Integral()

    templates_inclusive = get_projected_templates( templates, lead_ptrange =(None,None), subl_ptrange=subl_ptrange )
    templates_corr_inc = None
    if templates_corr is not None :
        templates_corr_inc = { }
        templates_corr_inc['leadPass'] = templates_corr['leadPass'][(reg[0], reg[1])]['Data'].ProjectionX('px_pass')
        templates_corr_inc['leadFail'] = templates_corr['leadFail'][(reg[0], reg[1])]['Data'].ProjectionX('px_fail')

    # all results should be unblinded
    ndim = 4

    (results_inclusive_stat_dataSR,results_inclusive_stat_dataSB, results_inclusive_stat_temp_tight, results_inclusive_stat_temp_loose, results_inclusive_stat_ff, results_inclusive_syst_bkg, results_inclusive_syst_temp) = run_diphoton_fit(templates_inclusive, gg_hist_inclusive, reg[0], reg[1], templates_corr=templates_corr_inc, lead_ptrange=(None,None), subl_ptrange=subl_ptrange, outputDir=outputDir, outputPrefix='__%s'%ch, systematics=systematics, fitvar=fitvar, ndim=ndim )

    namePostfix = '__ffcorr_%s__%s__%s-%s' %( ffcorr, ch, reg[0], reg[1] )

    save_templates( templates_inclusive, outputDir, lead_ptrange=(None,None), subl_ptrange=(None,None), namePostfix=namePostfix )

    namePostfix_statDataSR = '__statDataSR%s' %namePostfix
    save_results( results_inclusive_stat_dataSR, outputDir, namePostfix_statDataSR )

    namePostfix_statDataSB = '__statDataSB%s' %namePostfix
    save_results( results_inclusive_stat_dataSB, outputDir, namePostfix_statDataSB )

    namePostfix_statTempT = '__statTempTight%s' %namePostfix
    save_results( results_inclusive_stat_temp_tight, outputDir, namePostfix_statTempT )

    namePostfix_statTempL = '__statTempLoose%s' %namePostfix
    save_results( results_inclusive_stat_temp_loose, outputDir, namePostfix_statTempL )

    namePostfix_statFF = '__statTempFF%s' %namePostfix
    save_results( results_inclusive_stat_ff, outputDir, namePostfix_statFF )

    namePostfix_systBkg = '__systBkg%s' %namePostfix
    save_results( results_inclusive_syst_bkg, outputDir, namePostfix_systBkg )

    namePostfix_systTemp = '__systTemp%s' %namePostfix
    save_results( results_inclusive_syst_temp, outputDir, namePostfix_systTemp )

    # -----------------------
    # pt binned results
    # -----------------------
    for idx, ptmin in enumerate(ptbins[:-1] ) :
        ptmax = ptbins[idx+1]

        # put lead range together (expected by following code)
        if ptmax == ptbins[-1] : 
            lead_ptrange = ( ptmin, None )
        else :
            lead_ptrange = ( ptmin, ptmax )


        # project data hist
        if isinstance( gg_hist, dict )  and 'leadPass' in gg_hist :
            gg_hist_pt= {}
            gg_hist_pt['leadPass'] = gg_hist['leadPass'].ProjectionX( 'gg_hist_px_lead_pass_%d_%d' %(ptmin,ptmax), gg_hist['leadPass'].GetYaxis().FindBin(ptmin), gg_hist['leadPass'].GetYaxis().FindBin(ptmax)-1 )
            gg_hist_pt['leadFail'] = gg_hist['leadFail'].ProjectionX( 'gg_hist_px_lead_fail_%d_%d' %(ptmin,ptmax), gg_hist['leadFail'].GetYaxis().FindBin(ptmin), gg_hist['leadFail'].GetYaxis().FindBin(ptmax)-1 )
        else :
            gg_hist.GetZaxis().SetRange( gg_hist.GetZaxis().FindBin( ptmin), gg_hist.GetZaxis().FindBin( ptmax )-1 )
            gg_hist_pt = gg_hist.Project3D( 'yx' )

        # determine the proper
        # sublead range given
        # the input lead and
        # sublead 
        if subl_ptrange[0] is not None :
            subl_min = subl_ptrange[0]
        else :
            subl_min = 15
        if subl_ptrange[1] is not None :
            if lead_ptrange[1] is None :
                subl_max = subl_ptrange[1]
            elif lead_ptrange[1] < subl_ptrange[1] :
                subl_max = lead_ptrange[1]
            else :
                subl_max = subl_ptrange[1]
        else :
            subl_max = lead_ptrange[1]


        # get templates
        templates_pt = get_projected_templates( templates, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max ) )
        #print '**************************************FIX DATA TEMPLATES********************'
        #templates_pt['lead']['real'] = templates_inclusive['lead']['real']
        #templates_pt['subl']['real'] = templates_inclusive['subl']['real']
        templates_corr_pt = None
        if templates_corr is not None :
            templates_corr_pt = {}
            full_temp_pass = templates_corr['leadPass'][(reg[0], reg[1])]['Data']
            full_temp_fail = templates_corr['leadFail'][(reg[0], reg[1])]['Data']
            templates_corr_pt['leadPass'] = full_temp_pass.ProjectionX('px_pass_%d_%d'%( ptmin, ptmax ),  full_temp_pass.GetYaxis().FindBin(ptmin), full_temp_pass.GetYaxis().FindBin(ptmax)-1 )
            templates_corr_pt['leadFail'] = full_temp_fail.ProjectionX('px_fail_%d_%d'%( ptmin, ptmax ),  full_temp_fail.GetYaxis().FindBin(ptmin), full_temp_fail.GetYaxis().FindBin(ptmax)-1 )

        # all results should be unblinded
        ndim = 4

        # get results
        (results_pt_stat_dataSR,results_pt_stat_dataSB, results_pt_stat_temp_tight, results_pt_stat_temp_loose, results_pt_stat_ff, results_pt_syst_bkg, results_pt_syst_temp) = run_diphoton_fit(templates_pt, gg_hist_pt, reg[0], reg[1], templates_corr=templates_corr_pt, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max ), outputDir=outputDir, outputPrefix='__%s' %ch, systematics=systematics, ndim=ndim, fitvar=fitvar )

        namePostfix = '__ffcorr_%s__%s__%s-%s' %( ffcorr, ch, reg[0], reg[1] )

        if lead_ptrange[0] is not None :
            if lead_ptrange[1] is None :
                namePostfix += '__pt_%d-max' %lead_ptrange[0]
            else :
                namePostfix += '__pt_%d-%d' %(lead_ptrange[0], lead_ptrange[1] )

        if subl_ptrange[0] is not None :
            if subl_ptrange[1] is None :
                namePostfix += '__subpt_%d-max' %subl_ptrange[0]
            else :
                namePostfix += '__subpt_%d-%d' %(subl_ptrange[0], subl_ptrange[1] )

        save_templates( templates_pt, outputDir, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max), namePostfix=namePostfix )

        namePostfix_statDataSR= '__statDataSR%s' %namePostfix
        save_results( results_pt_stat_dataSR, outputDir, namePostfix_statDataSR )

        namePostfix_statDataSB= '__statDataSB%s' %namePostfix
        save_results( results_pt_stat_dataSB, outputDir, namePostfix_statDataSB )

        namePostfix_statTempT = '__statTempTight%s' %namePostfix
        save_results( results_pt_stat_temp_tight, outputDir, namePostfix_statTempT)

        namePostfix_statTempL = '__statTempLoose%s' %namePostfix
        save_results( results_pt_stat_temp_loose, outputDir, namePostfix_statTempL)

        namePostfix_statTempFF = '__statTempFF%s' %namePostfix
        save_results( results_pt_stat_ff, outputDir, namePostfix_statTempFF)

        namePostfix_systBkg = '__systBkg%s' %namePostfix
        save_results( results_pt_syst_bkg, outputDir, namePostfix_systBkg )

        namePostfix_systTemp = '__systTemp%s' %namePostfix
        save_results( results_pt_syst_temp, outputDir, namePostfix_systTemp)


# depricated , use classes
#def do_corrected_asymiso_fit( loose_iso_cuts = None, ptbins=[], subl_ptrange=(None,None), fitvar='sigmaIEIE', ch='mu', ffcorr='None', outputDir=None, systematics=None ) :
#
#    if loose_iso_cuts == None :
#        print 'Must provide a set of loose iso cuts'
#        return
#
#    binning = get_default_binning(fitvar)
#    samples = get_default_samples(ch)
#
#    real_template_str_iso = get_real_template_draw_commands(fitvar, ch)
#    fake_template_str_iso = get_fake_template_draw_commands(fitvar, ch)
#
#    templates_iso_reg = {}
#    templates_iso_reg['EB'] = {}
#    templates_iso_reg['EE'] = {}
#    templates_iso_reg['EB']['real'] = get_single_photon_template(real_template_str_iso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, sampMan=sampManLG )
#    templates_iso_reg['EE']['real'] = get_single_photon_template(real_template_str_iso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, sampMan=sampManLG )
#    templates_iso_reg['EB']['fake'] = get_single_photon_template(fake_template_str_iso, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, sampMan=sampManLLG )
#    templates_iso_reg['EE']['fake'] = get_single_photon_template(fake_template_str_iso, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, sampMan=sampManLLG )
#
#    
#    templates_noiso_reg = {}
#    templates_noiso_reg['EB'] = {}
#    templates_noiso_reg['EE'] = {}
#    templates_noiso_reg['EB']['real'] = get_single_photon_template(real_template_str_noiso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, sampMan=sampManLG  )
#    templates_noiso_reg['EE']['real'] = get_single_photon_template(real_template_str_noiso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, sampMan=sampManLG  )
#    templates_noiso_reg['EB']['fake'] = get_single_photon_template(fake_template_str_noiso, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, sampMan=sampManLLG )
#    templates_noiso_reg['EE']['fake'] = get_single_photon_template(fake_template_str_noiso, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, sampMan=sampManLLG )
#
#    templates_corr = None
#    if ffcorr != 'None' :
#        corr_template_str_leadFail_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=True,  cuts=ffcorr )
#        corr_template_str_leadFail_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=True, cuts=ffcorr )
#        corr_template_str_leadFail_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=False, cuts=ffcorr )
#        corr_template_str_leadPass_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=True, cuts=ffcorr )
#
#        templates_corr = {'leadPass' : {}, 'leadFail' : {}}
#        templates_corr['leadFail'][('EB','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EB','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadFail'][('EB','EE')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EB','EE')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadFail'][('EE','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadFail_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#        templates_corr['leadPass'][('EE','EB')] = get_correlated_fake_fake_templates( corr_template_str_leadPass_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, sampMan=sampManDataNOEV  )
#
#    regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB') ]
#
#    for reg in regions :
#
#        templates_leadiso = {}
#        templates_leadiso['lead'] = {}
#        templates_leadiso['subl'] = {}
#        templates_leadiso['lead']['real'] = templates_iso_reg[reg[0]]['real']
#        templates_leadiso['subl']['real'] = templates_noiso_reg[reg[1]]['real']
#        templates_leadiso['lead']['fake'] = templates_iso_reg[reg[0]]['fake']
#        templates_leadiso['subl']['fake'] = templates_noiso_reg[reg[1]]['fake']
#
#        templates_subliso = {}
#        templates_subliso['lead'] = {}
#        templates_subliso['subl'] = {}
#        templates_subliso['lead']['real'] = templates_noiso_reg[reg[0]]['real']
#        templates_subliso['subl']['real'] = templates_iso_reg[reg[1]]['real']
#        templates_subliso['lead']['fake'] = templates_noiso_reg[reg[0]]['fake']
#        templates_subliso['subl']['fake'] = templates_iso_reg[reg[1]]['fake']
#
#        templates_nom = {}
#        templates_nom['lead'] = {}
#        templates_nom['subl'] = {}
#        templates_nom['subl']['real'] = templates_subliso['subl']['real']
#        templates_nom['subl']['fake'] = templates_subliso['subl']['fake']
#        templates_nom['lead']['real'] = templates_leadiso['lead']['real']
#        templates_nom['lead']['fake'] = templates_leadiso['lead']['fake']
#
#        
#        # add regions onto the selection
#        gg_selection_leadiso = get_default_draw_commands(ch) + ' && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#        gg_selection_subliso = get_default_draw_commands(ch) + ' && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#        gg_selection_bothiso = get_default_draw_commands(ch) + ' && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
#
#        # add subl pt cuts onto the selection
#        if subl_ptrange[0] is not None :
#            if subl_ptrange[1] is None :
#                gg_selection_leadiso = gg_selection_leadiso + ' && pt_sublph12 > %d' %subl_ptrange[0]
#                gg_selection_subliso = gg_selection_subliso + ' && pt_sublph12 > %d' %subl_ptrange[0]
#                gg_selection_bothiso = gg_selection_bothiso + ' && pt_sublph12 > %d' %subl_ptrange[0]
#            else :
#                gg_selection_leadiso = gg_selection_leadiso + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(subl_ptrange[0], subl_ptrange[1] )
#                gg_selection_subliso = gg_selection_subliso + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(subl_ptrange[0], subl_ptrange[1] )
#                gg_selection_bothiso = gg_selection_bothiso + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(subl_ptrange[0], subl_ptrange[1] )
#
#        if fitvar == 'sigmaIEIE' :
#            # add object cuts to the selection
#
#            nom_iso_cuts_lead = 'chIsoCorr_leadph12 < %f && neuIsoCorr_leadph12 < %f && phoIsoCorr_leadph12 < %f '%( _chIso_cuts[reg[0]][0], _neuIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0])
#            nom_iso_cuts_subl = 'chIsoCorr_sublph12 < %f && neuIsoCorr_sublph12 < %f && phoIsoCorr_sublph12 < %f '%( _chIso_cuts[reg[1]][0], _neuIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0])
#
#            gg_selection_leadiso = gg_selection_leadiso + ' && ph_iso%d%d%d_n > 1 && %s ' %(loose_iso_cuts[0], loose_iso_cuts[1], loose_iso_cuts[2], nom_iso_cuts_lead )
#            gg_selection_subliso = gg_selection_subliso + ' && ph_iso%d%d%d_n > 1 && %s ' %(loose_iso_cuts[0], loose_iso_cuts[1], loose_iso_cuts[2], nom_iso_cuts_subl )
#
#            gg_selection_leadiso = gg_selection_leadiso + ' && chIsoCorr_sublph12 < %d && neuIsoCorr_sublph12 < %d && phoIsoCorr_sublph12 < %d ' %( loose_iso_cuts )
#            gg_selection_subliso = gg_selection_subliso + ' && chIsoCorr_leadph12 < %d && neuIsoCorr_leadph12 < %d && phoIsoCorr_leadph12 < %d ' %( loose_iso_cuts )
#
#            gg_selection_bothiso = gg_selection_bothiso + ' && ph_mediumNoSIEIENoEleVeto_n > 1 '
#
#        elif fitvar == 'chIsoCorr' :
#
#            nom_iso_cuts_lead = 'sieie_leadph12 < %f && neuIsoCorr_leadph12 < %f && phoIsoCorr_leadph12 < %f '%( _sieie_cuts[reg[0]][0], _neuIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0])
#            nom_iso_cuts_subl = 'sieie_sublph12 < %f && neuIsoCorr_sublph12 < %f && phoIsoCorr_sublph12 < %f '%( _sieie_cuts[reg[1]][0], _neuIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0])
#
#
#            gg_selection_leadiso = gg_selection_leadiso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_lead )
#            gg_selection_subliso = gg_selection_subliso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_subl )
#
#        
#            gg_selection_leadiso = gg_selection_leadiso + ' && sieie_sublph12 < %f && neuIsoCorr_sublph12 < %d && phoIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[1]][0], loose_iso_cuts[1], loose_iso_cuts[2] )
#            gg_selection_subliso = gg_selection_subliso + ' && sieie_leadph12 < %f && neuIsoCorr_leadph12 < %d && phoIsoCorr_leadph12 < %f ' %( _sieie_cuts[reg[0]][0],loose_iso_cuts[1], loose_iso_cuts[2] )
#
#            gg_selection_bothiso = gg_selection_bothiso + ' && sieie_leadph12 < %f && neuIsoCorr_leadph12 < %f && phoIsoCorr_leadph12 < %f && sieie_sublph12 < %f && neuIsoCorr_sublph12 < %f && phoIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[0]][0], _neuIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0],_sieie_cuts[reg[1]][0], _neuIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0] )
#
#        elif fitvar == 'neuIsoCorr' :
#
#            nom_iso_cuts_lead = 'sieie_leadph12 < %f && chIsoCorr_leadph12 < %f && phoIsoCorr_leadph12 < %f '%( _sieie_cuts[reg[0]][0], _chIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0])
#            nom_iso_cuts_subl = 'sieie_sublph12 < %f && chIsoCorr_sublph12 < %f && phoIsoCorr_sublph12 < %f '%( _sieie_cuts[reg[1]][0], _chIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0])
#
#
#            gg_selection_leadiso = gg_selection_leadiso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_lead )
#            gg_selection_subliso = gg_selection_subliso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_subl )
#
#        
#            gg_selection_leadiso = gg_selection_leadiso + ' && sieie_sublph12 < %f && chIsoCorr_sublph12 < %d && phoIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[1]][0], loose_iso_cuts[0], loose_iso_cuts[2] )
#            gg_selection_subliso = gg_selection_subliso + ' && sieie_leadph12 < %f && chIsoCorr_leadph12 < %d && phoIsoCorr_leadph12 < %f ' %( _sieie_cuts[reg[0]][0],loose_iso_cuts[0], loose_iso_cuts[2] )
#
#            gg_selection_bothiso = gg_selection_bothiso + ' && sieie_leadph12 < %f && chIsoCorr_leadph12 < %f && phoIsoCorr_leadph12 < %f && sieie_sublph12 < %f && chIsoCorr_sublph12 < %f && phoIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[0]][0], _chIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0],_sieie_cuts[reg[1]][0], _chIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0] )
#
#        elif fitvar == 'phoIsoCorr' :
#
#            nom_iso_cuts_lead = 'sieie_leadph12 < %f && chIsoCorr_leadph12 < %f && neuIsoCorr_leadph12 < %f '%( _sieie_cuts[reg[0]][0], _chIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0])
#            nom_iso_cuts_subl = 'sieie_sublph12 < %f && chIsoCorr_sublph12 < %f && neuIsoCorr_sublph12 < %f '%( _sieie_cuts[reg[1]][0], _chIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0])
#
#
#            gg_selection_leadiso = gg_selection_leadiso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_lead )
#            gg_selection_subliso = gg_selection_subliso + ' && ph_n > 1 && %s ' %( nom_iso_cuts_subl )
#
#        
#            gg_selection_leadiso = gg_selection_leadiso + ' && sieie_sublph12 < %f && chIsoCorr_sublph12 < %d && neuIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[1]][0], loose_iso_cuts[0], loose_iso_cuts[1] )
#            gg_selection_subliso = gg_selection_subliso + ' && sieie_leadph12 < %f && chIsoCorr_leadph12 < %d && neuIsoCorr_leadph12 < %f ' %( _sieie_cuts[reg[0]][0],loose_iso_cuts[0], loose_iso_cuts[1] )
#
#            gg_selection_bothiso = gg_selection_bothiso + ' && sieie_leadph12 < %f && chIsoCorr_leadph12 < %f && neuIsoCorr_leadph12 < %f && sieie_sublph12 < %f && chIsoCorr_sublph12 < %f && neuIsoCorr_sublph12 < %f ' %( _sieie_cuts[reg[0]][0], _chIso_cuts[reg[0]][0], _phoIso_cuts[reg[0]][0],_sieie_cuts[reg[1]][0], _chIso_cuts[reg[1]][0], _phoIso_cuts[reg[1]][0] )
#
#        # parse out the x and y binning
#        ybinn = binning[reg[1]]
#        xbinn = binning[reg[0]]
#
#        # variable given to TTree.Draw
#        #var = 'ph_pt[0]:ph_sigmaIEIE[1]:ph_sigmaIEIE[0]' #z:y:x
#        if fitvar == 'sigmaIEIE' :
#            var = 'pt_leadph12:sieie_sublph12:sieie_leadph12' #z:y:x
#        elif fitvar == 'chIsoCorr' :
#            var = 'pt_leadph12:chIsoCorr_sublph12:chIsoCorr_leadph12' #z:y:x
#        elif fitvar == 'neuIsoCorr' :
#            var = 'pt_leadph12:neuIsoCorr_sublph12:neuIsoCorr_leadph12' #z:y:x
#        elif fitvar == 'phoIsoCorr' :
#            var = 'pt_leadph12:phoIsoCorr_sublph12:phoIsoCorr_leadph12' #z:y:x
#
#        # get sample
#
#        # for certain channels, use a different SampleManager
#        if ch.count('invpixlead' ) :
#            print 'USE sampManDataInvL'
#            target_samp = sampManDataInvL.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw LeadIso                    '
#            print gg_selection_leadiso
#            print '---------------------------------'
#            gg_hist_leadiso = clone_sample_and_draw( target_samp[0], var, gg_selection_leadiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvL )
#            print '---------------------------------'
#            print ' Draw SublIso                    '
#            print gg_selection_subliso
#            print '---------------------------------'
#            gg_hist_subliso = clone_sample_and_draw( target_samp[0], var, gg_selection_subliso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvL )
#            print '---------------------------------'
#            print ' Draw BothIso                    '
#            print gg_selection_bothiso
#            print '---------------------------------'
#            gg_hist_bothiso = clone_sample_and_draw( target_samp[0], var, gg_selection_bothiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvL )
#
#        elif ch.count('invpixsubl' ) :
#            print 'USE sampManDataInvS'
#            target_samp = sampManDataInvS.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw LeadIso                    '
#            print gg_selection_leadiso
#            print '---------------------------------'
#            gg_hist_leadiso = clone_sample_and_draw( target_samp[0], var, gg_selection_leadiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvS )
#            print '---------------------------------'
#            print ' Draw SublIso                    '
#            print gg_selection_subliso
#            print '---------------------------------'
#            gg_hist_subliso = clone_sample_and_draw( target_samp[0], var, gg_selection_subliso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvS )
#            print '---------------------------------'
#            print ' Draw BothIso                    '
#            print gg_selection_bothiso
#            print '---------------------------------'
#            gg_hist_bothiso = clone_sample_and_draw( target_samp[0], var, gg_selection_bothiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataInvS )
#
#        elif ch.count('mu' ) :
#            print 'USE sampManDataNOEV'
#
#            target_samp = sampManDataNOEV.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw LeadIso                    '
#            print gg_selection_leadiso
#            print '---------------------------------'
#            gg_hist_leadiso = clone_sample_and_draw( target_samp[0], var, gg_selection_leadiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataNOEV )
#            print '---------------------------------'
#            print ' Draw SublIso                    '
#            print gg_selection_subliso
#            print '---------------------------------'
#            gg_hist_subliso = clone_sample_and_draw( target_samp[0], var, gg_selection_subliso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataNOEV )
#            print '---------------------------------'
#            print ' Draw BothIso                    '
#            print gg_selection_bothiso
#            print '---------------------------------'
#            gg_hist_bothiso = clone_sample_and_draw( target_samp[0], var, gg_selection_bothiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManDataNOEV )
#        else :
#            print 'USE sampManData'
#
#            target_samp = sampManData.get_samples(name=samples['target'])
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print ' Draw LeadIso                    '
#            print gg_selection_leadiso
#            print '---------------------------------'
#            gg_hist_leadiso = clone_sample_and_draw( target_samp[0], var, gg_selection_leadiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManData )
#            print '---------------------------------'
#            print ' Draw SublIso                    '
#            print gg_selection_subliso
#            print '---------------------------------'
#            gg_hist_subliso = clone_sample_and_draw( target_samp[0], var, gg_selection_subliso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManData )
#            print '---------------------------------'
#            print ' Draw BothIso                    '
#            print gg_selection_bothiso
#            print '---------------------------------'
#            gg_hist_bothiso = clone_sample_and_draw( target_samp[0], var, gg_selection_bothiso, ( xbinn[0], xbinn[1], xbinn[2], ybinn[0], ybinn[1], ybinn[2], 100, 0, 500 ),useSampMan=sampManData )
#        run_corr_calculation( templates_leadiso, templates_subliso, templates_nom, templates_corr, gg_hist_leadiso, gg_hist_subliso, gg_hist_bothiso, reg, ptbins, ch, fitvar, ffcorr, systematics=systematics,subl_ptrange=subl_ptrange,outputDir=outputDir )

def run_corr_calculation( templates_leadiso, templates_subliso, templates_nom, templates_corr, gg_hist_leadiso, gg_hist_subliso, gg_hist_bothiso, reg, ptbins, ch, fitvar, ffcorr, systematics=None, subl_ptrange=(None,None), outputDir=None, calcPostfix='' ) :

    # all results should be unblinded
    ndim = 4

    # -----------------------
    # inclusive result
    # -----------------------
    # project data hist
    if isinstance( gg_hist_leadiso, dict ) and 'leadPass' in gg_hist_leadiso :
        gg_hist_leadiso_inclusive = {}
        gg_hist_subliso_inclusive = {}
        gg_hist_bothiso_inclusive = {}

        gg_hist_leadiso_inclusive['leadPass'] = gg_hist_leadiso['leadPass'].ProjectionX('leadiso_px_pass')
        gg_hist_leadiso_inclusive['leadFail'] = gg_hist_leadiso['leadFail'].ProjectionX('leadiso_px_fail')
        gg_hist_subliso_inclusive['leadPass'] = gg_hist_subliso['leadPass'].ProjectionX('subliso_px_pass')
        gg_hist_subliso_inclusive['leadFail'] = gg_hist_subliso['leadFail'].ProjectionX('subliso_px_fail')
        gg_hist_bothiso_inclusive['leadPass'] = gg_hist_bothiso['leadPass'].ProjectionX('bothiso_px_pass')
        gg_hist_bothiso_inclusive['leadFail'] = gg_hist_bothiso['leadFail'].ProjectionX('bothiso_px_fail')

    else :

        gg_hist_leadiso_inclusive = gg_hist_leadiso.Project3D( 'yx' )
        gg_hist_subliso_inclusive = gg_hist_subliso.Project3D( 'yx' )
        gg_hist_bothiso_inclusive = gg_hist_bothiso.Project3D( 'yx' )

    templates_leadiso_inclusive = get_projected_templates( templates_leadiso, lead_ptrange = (None,None), subl_ptrange=subl_ptrange )
    templates_subliso_inclusive = get_projected_templates( templates_subliso, lead_ptrange = (None,None), subl_ptrange=subl_ptrange )
    templates_nom_inclusive     = get_projected_templates( templates_nom, lead_ptrange = (None,None), subl_ptrange=subl_ptrange )

    templates_corr_inc = None
    if templates_corr is not None :
        templates_corr_inc = {}
        templates_corr_inc['leadPass'] = templates_corr['leadPass'][(reg[0], reg[1])]['Data'].ProjectionX('px_pass')
        templates_corr_inc['leadFail'] = templates_corr['leadFail'][(reg[0], reg[1])]['Data'].ProjectionX('px_fail')

    (results_corr_stat_dataSR,results_corr_stat_dataSB, results_corr_stat_temp_tight, results_corr_stat_temp_loose, results_corr_stat_ff, results_corr_syst_bkg, results_corr_syst_temp)  = run_corrected_diphoton_fit(templates_leadiso_inclusive, templates_subliso_inclusive, gg_hist_leadiso_inclusive, gg_hist_subliso_inclusive, gg_hist_bothiso_inclusive, reg[0], reg[1], templates_corr = templates_corr_inc, fitvar=fitvar, lead_ptrange=(None,None), subl_ptrange=subl_ptrange, ndim=ndim,systematics=systematics)

    namePostfix = '__ffcorr_%s__%s__%s-%s__pt_%s-max__subpt_%s-max%s' %( ffcorr, ch,reg[0], reg[1], ptbins[0], ptbins[0], calcPostfix )

    save_templates( templates_nom_inclusive, outputDir, lead_ptrange=(None,None), subl_ptrange=(None,None),namePostfix=namePostfix )

    namePostfix_statDataSR = '__statDataSR%s'%namePostfix
    save_results( results_corr_stat_dataSR, outputDir, namePostfix_statDataSR)

    namePostfix_statDataSB = '__statDataSB%s'%namePostfix
    save_results( results_corr_stat_dataSB, outputDir, namePostfix_statDataSB)

    namePostfix_statTempT = '__statTempTight%s'%namePostfix
    save_results( results_corr_stat_temp_tight, outputDir, namePostfix_statTempT)

    namePostfix_statTempL = '__statTempLoose%s'%namePostfix
    save_results( results_corr_stat_temp_loose, outputDir, namePostfix_statTempL)

    namePostfix_statTempFF = '__statTempFF%s'%namePostfix
    save_results( results_corr_stat_ff, outputDir, namePostfix_statTempFF)

    namePostfix_systBkg = '__systBkg%s' %namePostfix
    save_results( results_corr_syst_bkg, outputDir, namePostfix_systBkg)

    namePostfix_systTemp = '__systTemp%s' %namePostfix
    save_results( results_corr_syst_temp, outputDir, namePostfix_systTemp)

    # -----------------------
    # pt binned results
    # -----------------------
    for idx, ptmin in enumerate(ptbins[:-1] ) :

        ptmax = ptbins[idx+1]

        # put lead range together (expected by following code)
        if ptmax == ptbins[-1] : 
            lead_ptrange = ( ptmin, None )
        else :
            lead_ptrange = ( ptmin, ptmax )

        # determine the proper
        # sublead range given
        # the input lead and
        # sublead 
        if subl_ptrange[0] is not None :
            subl_min = subl_ptrange[0]
        else :
            subl_min = 15
        if subl_ptrange[1] is not None :
            if lead_ptrange[1] is None :
                subl_max = subl_ptrange[1]
            elif lead_ptrange[1] < subl_ptrange[1] :
                subl_max = lead_ptrange[1]
            else :
                subl_max = subl_ptrange[1]
        else :
            subl_max = lead_ptrange[1]

        subl_max_name = str(subl_max)
        if subl_max == None :
            subl_max_name = 'max'

        if isinstance( gg_hist_leadiso, dict ) and 'leadPass' in gg_hist_leadiso :
            gg_hist_leadiso_pt = {}
            gg_hist_subliso_pt = {}
            gg_hist_bothiso_pt = {}

            gg_hist_leadiso_pt['leadPass'] = gg_hist_leadiso['leadPass'].ProjectionX( 'px_leadiso_pass_%d-%d' %(ptmin, ptmax), gg_hist_leadiso['leadPass'].GetYaxis().FindBin(ptmin), gg_hist_leadiso['leadPass'].GetYaxis().FindBin(ptmax) -1 )
            gg_hist_leadiso_pt['leadFail'] = gg_hist_leadiso['leadFail'].ProjectionX( 'px_leadiso_fail_%d-%d' %(ptmin, ptmax), gg_hist_leadiso['leadFail'].GetYaxis().FindBin(ptmin), gg_hist_leadiso['leadFail'].GetYaxis().FindBin(ptmax) -1 )
            gg_hist_subliso_pt['leadPass'] = gg_hist_subliso['leadPass'].ProjectionX( 'px_subliso_pass_%d-%d' %(ptmin, ptmax), gg_hist_subliso['leadPass'].GetYaxis().FindBin(ptmin), gg_hist_subliso['leadPass'].GetYaxis().FindBin(ptmax) -1 )
            gg_hist_subliso_pt['leadFail'] = gg_hist_subliso['leadFail'].ProjectionX( 'px_subliso_fail_%d-%d' %(ptmin, ptmax), gg_hist_subliso['leadFail'].GetYaxis().FindBin(ptmin), gg_hist_subliso['leadFail'].GetYaxis().FindBin(ptmax) -1 )
            gg_hist_bothiso_pt['leadPass'] = gg_hist_bothiso['leadPass'].ProjectionX( 'px_bothiso_pass_%d-%d' %(ptmin, ptmax), gg_hist_bothiso['leadPass'].GetYaxis().FindBin(ptmin), gg_hist_bothiso['leadPass'].GetYaxis().FindBin(ptmax) -1 )
            gg_hist_bothiso_pt['leadFail'] = gg_hist_bothiso['leadFail'].ProjectionX( 'px_bothiso_fail_%d-%d' %(ptmin, ptmax), gg_hist_bothiso['leadFail'].GetYaxis().FindBin(ptmin), gg_hist_bothiso['leadFail'].GetYaxis().FindBin(ptmax) -1 )
        else :
            # project data hist
            gg_hist_leadiso.GetZaxis().SetRange( gg_hist_leadiso.GetZaxis().FindBin( ptmin), gg_hist_leadiso.GetZaxis().FindBin( ptmax )-1 )
            gg_hist_leadiso_pt = gg_hist_leadiso.Project3D( 'yx' )

            gg_hist_subliso.GetZaxis().SetRange( gg_hist_subliso.GetZaxis().FindBin( ptmin), gg_hist_subliso.GetZaxis().FindBin( ptmax )-1 )
            gg_hist_subliso_pt = gg_hist_subliso.Project3D( 'yx' )

            gg_hist_bothiso.GetZaxis().SetRange( gg_hist_bothiso.GetZaxis().FindBin( ptmin), gg_hist_bothiso.GetZaxis().FindBin( ptmax )-1 )
            gg_hist_bothiso_pt = gg_hist_bothiso.Project3D( 'yx' )

            
        # all results should be unblinded
        ndim = 4

        # get templates
        templates_leadiso_pt = get_projected_templates( templates_leadiso, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max) )
        templates_subliso_pt = get_projected_templates( templates_subliso, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max) )
        templates_nom_pt = get_projected_templates( templates_nom, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max) )

        #print '*******************************FIX DATA TEMPLATES**********************'
        #templates_leadiso_pt['lead']['real'] = templates_leadiso_inclusive['lead']['real']
        #templates_leadiso_pt['subl']['real'] = templates_leadiso_inclusive['subl']['real']
        #templates_subliso_pt['lead']['real'] = templates_subliso_inclusive['lead']['real']
        #templates_subliso_pt['subl']['real'] = templates_subliso_inclusive['subl']['real']
        #templates_nom_pt['lead']['real'] = templates_nom_inclusive['lead']['real']
        #templates_nom_pt['subl']['real'] = templates_nom_inclusive['subl']['real']

        templates_corr_pt = None
        if templates_corr is not None :
            templates_corr_pt = {}
            full_temp_pass = templates_corr['leadPass'][(reg[0], reg[1])]['Data']
            full_temp_fail = templates_corr['leadFail'][(reg[0], reg[1])]['Data']
            templates_corr_pt['leadPass'] = full_temp_pass.ProjectionX('px_pass_%d_%d'%( ptmin,ptmax),  full_temp_pass.GetYaxis().FindBin(ptmin), full_temp_pass.GetYaxis().FindBin(ptmax)-1 )
            templates_corr_pt['leadFail'] = full_temp_fail.ProjectionX('px_fail_%d_%d'%( ptmin,ptmax),  full_temp_fail.GetYaxis().FindBin(ptmin), full_temp_fail.GetYaxis().FindBin(ptmax)-1 )

        # get results
        (results_corr_pt_stat_dataSR,results_corr_pt_stat_dataSB, results_corr_pt_stat_temp_tight, results_corr_pt_stat_temp_loose, results_corr_pt_stat_ff, results_corr_pt_syst_bkg, results_corr_pt_syst_temp) = run_corrected_diphoton_fit(templates_leadiso_pt, templates_subliso_pt, gg_hist_leadiso_pt, gg_hist_subliso_pt, gg_hist_bothiso_pt, reg[0], reg[1], templates_corr=templates_corr_pt, fitvar=fitvar, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min, subl_max), ndim=ndim, systematics=systematics)

        namePostfix = '__ffcorr_%s__%s__%s-%s' %( ffcorr, ch, reg[0], reg[1] )

        if lead_ptrange[0] is not None :
            if lead_ptrange[1] is None :
                namePostfix += '__pt_%d-max' %lead_ptrange[0]
            else :
                namePostfix += '__pt_%d-%d' %(lead_ptrange[0], lead_ptrange[1] )

        if subl_ptrange[0] is not None :
            if subl_ptrange[1] is None :
                namePostfix += '__subpt_%d-max' %subl_ptrange[0]
            else :
                namePostfix += '__subpt_%d-%d' %(subl_ptrange[0], subl_ptrange[1] )

        namePostfix += calcPostfix

        save_templates( templates_nom_pt, outputDir, lead_ptrange=lead_ptrange, subl_ptrange=(subl_min,subl_max), namePostfix=namePostfix)

        namePostfix_statDataSR = '__statDataSR%s' %namePostfix
        save_results( results_corr_pt_stat_dataSR, outputDir, namePostfix_statDataSR)

        namePostfix_statDataSB = '__statDataSB%s' %namePostfix
        save_results( results_corr_pt_stat_dataSB, outputDir, namePostfix_statDataSB)

        namePostfix_statTempT = '__statTempTight%s' %namePostfix
        save_results( results_corr_pt_stat_temp_tight, outputDir, namePostfix_statTempT)

        namePostfix_statTempL = '__statTempLoose%s' %namePostfix
        save_results( results_corr_pt_stat_temp_loose, outputDir, namePostfix_statTempL)

        namePostfix_statTempFF = '__statTempFF%s' %namePostfix
        save_results( results_corr_pt_stat_ff, outputDir, namePostfix_statTempFF)

        namePostfix_systBkg = '__systBkg%s' %namePostfix
        save_results( results_corr_pt_syst_bkg, outputDir, namePostfix_systBkg)

        namePostfix_systTemp = '__systTemp%s' %namePostfix
        save_results( results_corr_pt_syst_temp, outputDir, namePostfix_systTemp)

# depricated
#def do_closure_fit( iso_cuts_lead=None, iso_cuts_subl=None, ptbins=[], subl_ptrange=(None,None), ch='mu', ngen=None, corr_factor=0.0, outputDir=None ) :
#
#    if ngen is None :
#        ngen = { 'RF' : 10000, 'FR' : 10000, 'FF' : 10000 }
#
#    binning = get_default_binning()
#    samples = get_default_samples(ch)
#
#    # generate templates for both EB and EE
#    fitvar = 'sigmaIEIE'
#    real_template_str = get_real_template_draw_commands(fitvar, ch) + ' && %s' %iso_cuts_lead
#    fake_template_str = get_fake_template_draw_commands(fitvar, ch) + ' && %s' %iso_cuts_lead
#
#    templates_reg = {}
#    templates_reg['EB'] = {}
#    templates_reg['EE'] = {}
#    print '***********************************FIX DATA TEMPLATES************************************'
#    #templates_reg['EB']['real'] = get_single_photon_template(real_template_str, binning['EB'], samples['real'], 'EB', sampMan=sampManLG )
#    #templates_reg['EE']['real'] = get_single_photon_template(real_template_str, binning['EE'], samples['real'], 'EE', sampMan=sampManLG )
#    templates_reg['EB']['real'] = get_single_photon_template(real_template_str, binning['EB'], samples['real'], 'EB', sampMan=sampManLLG )
#    templates_reg['EE']['real'] = get_single_photon_template(real_template_str, binning['EE'], samples['real'], 'EE', sampMan=sampManLLG )
#    templates_reg['EB']['fake'] = get_single_photon_template(fake_template_str, binning['EB'], samples['fake'], 'EB', sampMan=sampManLLG)
#    templates_reg['EE']['fake'] = get_single_photon_template(fake_template_str, binning['EE'], samples['fake'], 'EE', sampMan=sampManLLG)
#
#    regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB'), ('EE', 'EE') ]
#    for reg in regions :
#
#        # convert from regions to lead/subl
#        templates = {}
#        templates['lead'] = {}
#        templates['subl'] = {}
#        templates['lead']['real'] = templates_reg[reg[0]]['real']
#        templates['subl']['real'] = templates_reg[reg[1]]['real']
#        templates['lead']['fake'] = templates_reg[reg[0]]['fake']
#        templates['subl']['fake'] = templates_reg[reg[1]]['fake']
#
#        templates_inclusive = get_projected_templates( templates, lead_ptrange = (None,None), subl_ptrange=subl_ptrange )
#
#        results_inclusive = run_generated_diphoton_fit(templates_inclusive, reg[0], reg[1], ngen, lead_ptrange=(None,None), subl_ptrange=subl_ptrange, corr_factor=corr_factor, outputDir=outputDir, outputPrefix='__%s'%ch )
#
#        #namePostfix = '__%s__%s-%s' %( ch, reg[0], reg[1] )
#        #save_templates( templates_inclusive, outputDir, lead_ptrange=(None,None), subl_ptrange=(None,None), namePostfix=namePostfix )
#        #save_results( results_inclusive, outputDir, namePostfix )
#
#        # -----------------------
#        # pt binned results
#        # -----------------------
#        for idx, ptmin in enumerate(ptbins[:-1] ) :
#            ptmax = ptbins[idx+1]
#
#            # put lead range together (expected by following code)
#            if ptmax == ptbins[-1] : 
#                lead_ptrange = ( ptmin, None )
#            else :
#                lead_ptrange = ( ptmin, ptmax )
#
#            # determine the proper
#            # sublead range given
#            # the input lead and
#            # sublead 
#            if subl_ptrange[0] is not None :
#                subl_min = subl_ptrange[0]
#            else :
#                subl_min = 15
#            if subl_ptrange[1] is not None :
#                if lead_ptrange[1] is None :
#                    subl_max = subl_ptrange[1]
#                elif lead_ptrange[1] < subl_ptrange[1] :
#                    subl_max = lead_ptrange[1]
#                else :
#                    subl_max = subl_ptrange[1]
#            else :
#                subl_max = lead_ptrange[1]
#
#            subl_max_name = str(subl_max)
#            if subl_max == None :
#                subl_max_name = 'max'
#
#            print 'ptleadmin = %d, ptleadmax = %d, ptsublmin = %d, ptsublmax = %s, region = %s-%s' %( ptmin, ptmax, subl_min, subl_max_name, reg[0], reg[1] )
#            # get templates
#            templates_pt = get_projected_templates( templates, lead_ptrange=lead_ptrange, subl_ptrange=(15, lead_ptrange[1] ) )
#
#            # get results
#            results_pt = run_generated_diphoton_fit(templates_pt, reg[0], reg[1],ngen, lead_ptrange=lead_ptrange, subl_ptrange=subl_ptrange, corr_factor=corr_factor, outputDir=outputDir, outputPrefix='__%s' %ch )
#
#            #namePostfix = '__%s__%s-%s' %( ch, reg[0], reg[1] )
#            #if lead_ptrange[0] is not None :
#            #    if lead_ptrange[1] is None :
#            #        namePostfix += '__pt_%d-max' %lead_ptrange[0]
#            #    else :
#            #        namePostfix += '__pt_%d-%d' %(lead_ptrange[0], lead_ptrange[1] )
#
#            #if subl_ptrange[0] is not None :
#            #    if subl_ptrange[1] is None :
#            #        namePostfix += '__subpt_%d-max' %subl_ptrange[0]
#            #    else :
#            #        namePostfix += '__subpt_%d-%d' %(subl_ptrange[0], subl_ptrange[1] )
#
#            #save_templates( templates_pt, outputDir, lead_ptrange=lead_ptrange, subl_ptrange=(15, lead_ptrange[1]), namePostfix=namePostfix )
#            #save_results( results_pt, outputDir, namePostfix )


def update_asym_results( results_leadiso, results_subliso ) :
        
    iso_eff_subl = (results_subliso['template_int_subl_fake_tight']+results_subliso['template_int_subl_fake_loose'])/(results_leadiso['template_int_subl_fake_tight']+results_leadiso['template_int_subl_fake_loose'])
    iso_eff_lead = (results_leadiso['template_int_lead_fake_tight']+results_leadiso['template_int_lead_fake_loose'])/(results_subliso['template_int_lead_fake_tight']+results_subliso['template_int_lead_fake_loose'])

    results_leadiso['iso_eff_subl'] = iso_eff_subl
    results_subliso['iso_eff_lead'] = iso_eff_lead

    results_leadiso['Npred_RF_TT_scaled'] = results_leadiso['Npred_RF_TT']*iso_eff_subl
    results_leadiso['Npred_FR_TT_scaled'] = results_leadiso['Npred_FR_TT']*iso_eff_subl
    results_leadiso['Npred_FF_TT_scaled'] = results_leadiso['Npred_FF_TT']*iso_eff_subl

    results_leadiso['Npred_RF_TL_scaled'] = results_leadiso['Npred_RF_TL']*iso_eff_subl
    results_leadiso['Npred_FR_TL_scaled'] = results_leadiso['Npred_FR_TL']*iso_eff_subl
    results_leadiso['Npred_FF_TL_scaled'] = results_leadiso['Npred_FF_TL']*iso_eff_subl

    results_leadiso['Npred_RF_LT_scaled'] = results_leadiso['Npred_RF_LT']*iso_eff_subl
    results_leadiso['Npred_FR_LT_scaled'] = results_leadiso['Npred_FR_LT']*iso_eff_subl
    results_leadiso['Npred_FF_LT_scaled'] = results_leadiso['Npred_FF_LT']*iso_eff_subl

    results_leadiso['Npred_RF_LL_scaled'] = results_leadiso['Npred_RF_LL']*iso_eff_subl
    results_leadiso['Npred_FR_LL_scaled'] = results_leadiso['Npred_FR_LL']*iso_eff_subl
    results_leadiso['Npred_FF_LL_scaled'] = results_leadiso['Npred_FF_LL']*iso_eff_subl

    results_subliso['Npred_RF_TT_scaled'] = results_subliso['Npred_RF_TT']*iso_eff_lead
    results_subliso['Npred_FR_TT_scaled'] = results_subliso['Npred_FR_TT']*iso_eff_lead
    results_subliso['Npred_FF_TT_scaled'] = results_subliso['Npred_FF_TT']*iso_eff_lead

    results_subliso['Npred_RF_TL_scaled'] = results_subliso['Npred_RF_TL']*iso_eff_lead
    results_subliso['Npred_FR_TL_scaled'] = results_subliso['Npred_FR_TL']*iso_eff_lead
    results_subliso['Npred_FF_TL_scaled'] = results_subliso['Npred_FF_TL']*iso_eff_lead

    results_subliso['Npred_RF_LT_scaled'] = results_subliso['Npred_RF_LT']*iso_eff_lead
    results_subliso['Npred_FR_LT_scaled'] = results_subliso['Npred_FR_LT']*iso_eff_lead
    results_subliso['Npred_FF_LT_scaled'] = results_subliso['Npred_FF_LT']*iso_eff_lead

    results_subliso['Npred_RF_LL_scaled'] = results_subliso['Npred_RF_LL']*iso_eff_lead
    results_subliso['Npred_FR_LL_scaled'] = results_subliso['Npred_FR_LL']*iso_eff_lead
    results_subliso['Npred_FF_LL_scaled'] = results_subliso['Npred_FF_LL']*iso_eff_lead

def get_projected_templates( templates, lead_ptrange=(None,None), subl_ptrange=(None,None) ) :

    templates_proj = {}
    templates_proj['lead'] = {}
    templates_proj['subl'] = {}

    # project in a range
    if lead_ptrange[0] is not None :
        for rf, hist_entries in templates['lead'].iteritems() :
            templates_proj['lead'][rf] = {}
            for hist_type, hist in hist_entries.iteritems() : 
                if hist is None :
                    templates_proj['lead'][rf][hist_type] = None
                else :
                    if lead_ptrange[1] is None :
                        templates_proj['lead'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_%d-max' %( lead_ptrange[0] ), hist.GetYaxis().FindBin( lead_ptrange[0] ) )
                    else :
                        templates_proj['lead'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_%d-%d' %( lead_ptrange[0], lead_ptrange[1] ), hist.GetYaxis().FindBin( lead_ptrange[0] ), hist.GetYaxis().FindBin( lead_ptrange[1] )-1 )

    else : # project inclusive
        for rf, hist_entries in templates['lead'].iteritems() :
            templates_proj['lead'][rf] = {}
            for hist_type, hist in hist_entries.iteritems() : 
                if hist is not None :
                    templates_proj['lead'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_inclusive' )
                else :
                    templates_proj['lead'][rf][hist_type] = None


    if subl_ptrange[0] is not None : # project in a range
        for rf, hist_entries in templates['subl'].iteritems() :
            templates_proj['subl'][rf] = {}
            for hist_type, hist in hist_entries.iteritems() : 
                if hist is None :
                    templates_proj['subl'][rf][hist_type] = None
                else :
                    if subl_ptrange[1] is None :
                        templates_proj['subl'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_%d-max' %subl_ptrange[0], hist.GetYaxis().FindBin( subl_ptrange[0] ) )
                    else :
                        templates_proj['subl'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_%d-%d' %(subl_ptrange[0],subl_ptrange[1]), hist.GetYaxis().FindBin( subl_ptrange[0] ) , hist.GetYaxis().FindBin( subl_ptrange[1] )-1 )
    else : # project inclusive
        for rf, hist_entries in templates['subl'].iteritems() :
            templates_proj['subl'][rf] = {}
            for hist_type, hist in hist_entries.iteritems() : 
                if hist is None :
                    templates_proj['subl'][rf][hist_type] = None
                else :
                    templates_proj['subl'][rf][hist_type] = hist.ProjectionX( hist.GetName()+'_px_inclusive' )

    return templates_proj


def run_corrected_diphoton_fit( templates_leadiso, templates_subliso, gg_hist_leadiso, gg_hist_subliso, gg_hist_bothiso, lead_reg, subl_reg, templates_corr=None, fitvar=None, lead_ptrange=(None,None), subl_ptrange=(None,None), ndim=3, systematics=None ) :

    accept_reg = ['EB', 'EE']
    if lead_reg not in accept_reg :
        print 'Lead region does not make sense'
        return
    if subl_reg not in accept_reg :
        print 'Subl region does not make sense'
        return

    # get the defaults
    samples = get_default_samples()
    plotbinning = get_default_binning()
    cuts = get_default_cuts(var=fitvar)

    bins_lead_loose = ( None, None )
    bins_lead_tight = ( None, None )
    if isinstance( gg_hist_leadiso, dict ) :

        # Find the bins corresponding to the cuts
        # lead photon on X axis, subl on Y axis
        bins_subl_tight = ( gg_hist_leadiso['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['tight'][0] ), gg_hist_leadiso['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['tight'][1] ) )
        bins_subl_loose = ( gg_hist_leadiso['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['loose'][0] ), gg_hist_leadiso['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['loose'][1] ) )

        # Integrate to the the data in the four regions
        Ndata_TT_leadiso = gg_hist_leadiso['leadPass'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL_leadiso = gg_hist_leadiso['leadPass'].Integral( bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT_leadiso = gg_hist_leadiso['leadFail'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL_leadiso = gg_hist_leadiso['leadFail'].Integral( bins_subl_loose[0], bins_subl_loose[1] )

        Ndata_TT_subliso = gg_hist_subliso['leadPass'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL_subliso = gg_hist_subliso['leadPass'].Integral( bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT_subliso = gg_hist_subliso['leadFail'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL_subliso = gg_hist_subliso['leadFail'].Integral( bins_subl_loose[0], bins_subl_loose[1] )

        Ndata_TT_bothiso = gg_hist_bothiso['leadPass'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        
    else :

        # Find the bins corresponding to the cuts
        # lead photon on X axis, subl on Y axis
        bins_lead_tight = ( gg_hist_leadiso.GetXaxis().FindBin( cuts[lead_reg]['tight'][0] ), gg_hist_leadiso.GetXaxis().FindBin( cuts[lead_reg]['tight'][1] ) )
        bins_lead_loose = ( gg_hist_leadiso.GetXaxis().FindBin( cuts[lead_reg]['loose'][0] ), gg_hist_leadiso.GetXaxis().FindBin( cuts[lead_reg]['loose'][1] ) )
        bins_subl_tight = ( gg_hist_leadiso.GetYaxis().FindBin( cuts[subl_reg]['tight'][0] ), gg_hist_leadiso.GetYaxis().FindBin( cuts[subl_reg]['tight'][1] ) )
        bins_subl_loose = ( gg_hist_leadiso.GetYaxis().FindBin( cuts[subl_reg]['loose'][0] ), gg_hist_leadiso.GetYaxis().FindBin( cuts[subl_reg]['loose'][1] ) )

        # Integrate to the the data in the four regions
        Ndata_TT_leadiso = gg_hist_leadiso.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL_leadiso = gg_hist_leadiso.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT_leadiso = gg_hist_leadiso.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL_leadiso = gg_hist_leadiso.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_loose[0], bins_subl_loose[1] )

        Ndata_TT_subliso = gg_hist_subliso.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL_subliso = gg_hist_subliso.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT_subliso = gg_hist_subliso.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL_subliso = gg_hist_subliso.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_loose[0], bins_subl_loose[1] )

        Ndata_TT_bothiso = gg_hist_bothiso.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_tight[0], bins_subl_tight[1] )


    # arragnge the cuts by region
    eff_cuts = {}
    eff_cuts['lead'] = {}
    eff_cuts['subl'] = {}
    eff_cuts['lead']['tight'] = cuts[lead_reg]['tight']
    eff_cuts['lead']['loose'] = cuts[lead_reg]['loose']
    eff_cuts['subl']['tight'] = cuts[subl_reg]['tight']
    eff_cuts['subl']['loose'] = cuts[subl_reg]['loose']

    # get template integrals
    #int_leadiso = get_template_integrals( templates_leadiso, eff_cuts )
    #int_subliso = get_template_integrals( templates_subliso, eff_cuts )
    (stat_int_leadiso, syst_int_leadiso) = get_template_integrals( templates_leadiso, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar, systematics=systematics )
    (stat_int_subliso, syst_int_subliso) = get_template_integrals( templates_subliso, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar, systematics=systematics )

    if stat_int_leadiso['subl']['fake']['tight'] != 0 :
        iso_eff_subl_tight = stat_int_subliso['subl']['fake']['tight'] / stat_int_leadiso['subl']['fake']['tight']
    else :
        iso_eff_subl_tight = ufloat( 0, 0)
    if stat_int_leadiso['subl']['fake']['loose'] != 0 :
        iso_eff_subl_loose = stat_int_subliso['subl']['fake']['loose'] / stat_int_leadiso['subl']['fake']['loose']
    else :
        iso_eff_subl_loose = ufloat( 0, 0)
    if stat_int_subliso['lead']['fake']['tight'] != 0 :
        iso_eff_lead_tight = stat_int_leadiso['lead']['fake']['tight'] / stat_int_subliso['lead']['fake']['tight']
    else :
        iso_eff_lead_tight = ufloat( 0, 0)
    if stat_int_subliso['lead']['fake']['loose'] != 0 :
        iso_eff_lead_loose = stat_int_leadiso['lead']['fake']['loose'] / stat_int_subliso['lead']['fake']['loose']
    else :
        iso_eff_lead_loose = ufloat( 0, 0)


    #-----------------------------------------
    # Use data with loosened iso on the Loose photon
    # Multiply by the efficiency of the loosened iso
    #-----------------------------------------
     
    # lead has loosened iso
    # Correct data in LT region by loosening isolation on the lead photon 
    # and correct by the efficiency of the loosened selection
    Ncorr_LT         = Ndata_LT_subliso * iso_eff_lead_loose
    Ncorr_LL_subliso = Ndata_LL_subliso * iso_eff_lead_loose
    Ncorr_TT_subliso = Ndata_TT_subliso * iso_eff_lead_loose

    # subl has loosened iso
    # correct data in TL region by loosening isolation on the subl photon
    # and correct by the efficiency of the loosened selection
    Ncorr_TL         = Ndata_TL_leadiso * iso_eff_subl_loose
    Ncorr_LL_leadiso = Ndata_LL_leadiso * iso_eff_subl_loose
    Ncorr_TT_leadiso = Ndata_TT_leadiso * iso_eff_subl_loose

    # use the average of the two
    Ncorr_LL = ( Ncorr_LL_leadiso + Ncorr_LL_subliso )/2.
    Ncorr_TT = ( Ncorr_TT_leadiso + Ncorr_TT_subliso )/2.

    print 'NData both iso TT = %d' %Ndata_TT_bothiso
    print 'NData orig leadiso , TT = %d, TL = %d, LT = %d, LL = %d' %( Ndata_TT_leadiso, Ndata_TL_leadiso, Ndata_LT_leadiso, Ndata_LL_leadiso )
    print 'NData orig subliso , TT = %d, TL = %d, LT = %d, LL = %d' %( Ndata_TT_subliso, Ndata_TL_subliso, Ndata_LT_subliso, Ndata_LL_subliso )
    print 'iso_eff_subl_tight = %s, iso_eff_subl_loose = %s, iso_eff_lead_tight = %s, iso_eff_lead_loose= %s' %( iso_eff_subl_tight, iso_eff_subl_loose, iso_eff_lead_tight, iso_eff_subl_loose )
    print 'NData corr, TL = %s, LT = %s, LLlead = %s, LLsubl = %s, LL = %s, TTlead = %s, TTsubl = %s, TT = %s ' %( Ncorr_TL, Ncorr_LT, Ncorr_LL_leadiso, Ncorr_LL_subliso, Ncorr_LL, Ncorr_TT_leadiso, Ncorr_TT_subliso, Ncorr_TT )

    templates_comb = {}
    templates_comb['lead'] = {}
    templates_comb['subl'] = {}
    templates_comb['lead']['real'] = templates_leadiso['lead']['real']
    templates_comb['lead']['fake'] = templates_leadiso['lead']['fake']
    templates_comb['subl']['real'] = templates_subliso['subl']['real']
    templates_comb['subl']['fake'] = templates_subliso['subl']['fake']

    # get 2-d efficiencies from 1-d inputs
    eff_results = generate_2d_efficiencies( templates_comb, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar, systematics=systematics )

    if templates_corr is not None :

        eff_ff_2d_stat, eff_ff_2d_syst = generate_2d_corr_efficiencies( templates_corr, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar )

        print 'REPLACE FF with correlated templates'
        print 'eff_FF_TT before = %s, after = %s (tight unc)' %( eff_results['stat_tight']['eff_FF_TT'], eff_ff_2d_stat['eff_FF_TT'] )
        print 'eff_FF_TL before = %s, after = %s (tight unc)' %( eff_results['stat_tight']['eff_FF_TL'], eff_ff_2d_stat['eff_FF_TL'] )
        print 'eff_FF_LT before = %s, after = %s (tight unc)' %( eff_results['stat_tight']['eff_FF_LT'], eff_ff_2d_stat['eff_FF_LT'] )
        print 'eff_FF_LL before = %s, after = %s (tight unc)' %( eff_results['stat_tight']['eff_FF_LL'], eff_ff_2d_stat['eff_FF_LL'] )

        # for correlated FF templates
        # the uncertainties from 1-d templates
        # don't apply.  Set those to zero
        eff_results['stat_tight']['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )

        # make a new uncertainty
        # with fake-fake uncertainties
        eff_results['stat_ff'] = {}
        eff_results['stat_ff']['eff_FF_TT'] = eff_ff_2d_stat['eff_FF_TT']
        eff_results['stat_ff']['eff_FF_TL'] = eff_ff_2d_stat['eff_FF_TL']
        eff_results['stat_ff']['eff_FF_LT'] = eff_ff_2d_stat['eff_FF_LT']
        eff_results['stat_ff']['eff_FF_LL'] = eff_ff_2d_stat['eff_FF_LL']

        # put in all of the other values, use stat_tight as template
        eff_results['stat_ff']['eff_RR_TT'] = ufloat( eff_results['stat_tight']['eff_RR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_TL'] = ufloat( eff_results['stat_tight']['eff_RR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LT'] = ufloat( eff_results['stat_tight']['eff_RR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LL'] = ufloat( eff_results['stat_tight']['eff_RR_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_RF_TT'] = ufloat( eff_results['stat_tight']['eff_RF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_TL'] = ufloat( eff_results['stat_tight']['eff_RF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LT'] = ufloat( eff_results['stat_tight']['eff_RF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LL'] = ufloat( eff_results['stat_tight']['eff_RF_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_FR_TT'] = ufloat( eff_results['stat_tight']['eff_FR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_TL'] = ufloat( eff_results['stat_tight']['eff_FR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LT'] = ufloat( eff_results['stat_tight']['eff_FR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LL'] = ufloat( eff_results['stat_tight']['eff_FR_LL'].n, 0.0 )
        
    else :
        # put in all of the other values, use stat_tight as template
        eff_results['stat_ff'] = {}
        eff_results['stat_ff']['eff_FF_TT'] = ufloat( eff_results['stat_tight']['eff_FF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_TL'] = ufloat( eff_results['stat_tight']['eff_FF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_LT'] = ufloat( eff_results['stat_tight']['eff_FF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_LL'] = ufloat( eff_results['stat_tight']['eff_FF_LL'].n, 0.0 )

        eff_results['stat_ff']['eff_RR_TT'] = ufloat( eff_results['stat_tight']['eff_RR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_TL'] = ufloat( eff_results['stat_tight']['eff_RR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LT'] = ufloat( eff_results['stat_tight']['eff_RR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LL'] = ufloat( eff_results['stat_tight']['eff_RR_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_RF_TT'] = ufloat( eff_results['stat_tight']['eff_RF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_TL'] = ufloat( eff_results['stat_tight']['eff_RF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LT'] = ufloat( eff_results['stat_tight']['eff_RF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LL'] = ufloat( eff_results['stat_tight']['eff_RF_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_FR_TT'] = ufloat( eff_results['stat_tight']['eff_FR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_TL'] = ufloat( eff_results['stat_tight']['eff_FR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LT'] = ufloat( eff_results['stat_tight']['eff_FR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LL'] = ufloat( eff_results['stat_tight']['eff_FR_LL'].n, 0.0 )
        
    eff_2d_nouncert = {}
    for key, val in eff_results['stat_tight'].iteritems() :
        if type( val ) == type( ufloat(0,0) ) :
            eff_2d_nouncert[key] = ufloat( val.n, 0 )
        else :
            eff_2d_nouncert[key] =  val


    #Broken
    if ndim == 3 :
        datacorr = {}
        datacorr['TL'] = Ncorr_TL
        datacorr['LT'] = Ncorr_LT
        datacorr['LL'] = Ncorr_LL

        datacorr_nostat = {}
        datacorr_nostat['TL'] = ufloat( Ncorr_TL.n, 0.0 )
        datacorr_nostat['LT'] = ufloat( Ncorr_LT.n, 0.0 )
        datacorr_nostat['LL'] = ufloat( Ncorr_LL.n, 0.0 )

        results_stat_data       = run_fit( datacorr, eff_2d_nouncert )
        results_stat_temp_tight = run_fit( datacorr_nostat, eff_results['stat_tight'] )
        results_stat_temp_loose = run_fit( datacorr_nostat, eff_results['stat_loose'] )
        results_stat_ff         = run_fit( datacorr_nostat, eff_results['stat_ff'] )
        results_syst_bkg        = run_fit( datacorr_nostat, eff_results['syst_bkg'] )
        results_syst_temp       = run_fit( datacorr_nostat, eff_results['syst_temp'] )

        datacorr['TT'] = ufloat(0, 0)

        text_results_stat_data       = collect_results( results_stat_data      , datacorr, eff_2d_nouncert , templates_comb, eff_cuts, ndim)
        text_results_stat_temp_tight = collect_results( results_stat_temp_tight, datacorr, eff_results['stat_tight']     , templates_comb, eff_cuts, ndim)
        text_results_stat_temp_loose = collect_results( results_stat_temp_loose, datacorr, eff_results['stat_loose']     , templates_comb, eff_cuts, ndim)
        text_results_stat_ff         = collect_results( results_stat_ff        , datacorr, eff_results['stat_ff'   ]     , templates_comb, eff_cuts, ndim)
        text_results_syst_bkg        = collect_results( results_syst_bkg       , datacorr, eff_results['syst_bkg'] , templates_comb, eff_cuts, ndim)
        text_results_syst_temp       = collect_results( results_syst_temp      , datacorr, eff_results['syst_temp'], templates_comb, eff_cuts, ndim)

        
        #Broken
        return text_results_stat_data, text_results_stat_temp_tight, text_results_stat_temp_loose, text_results_stat_ff, text_results_syst_bkg, text_results_syst_temp

    else :

        # keep all data uncertainties for storing
        datacorr = {}
        datacorr['TT'] = ufloat( Ndata_TT_bothiso, math.sqrt(Ndata_TT_bothiso))
        datacorr['TL'] = Ncorr_TL
        datacorr['LT'] = Ncorr_LT
        datacorr['LL'] = Ncorr_LL

        # only consider uncertainty from the SR
        datacorrSR = {}
        datacorrSR['TT'] = ufloat( Ndata_TT_bothiso, math.sqrt(Ndata_TT_bothiso))
        datacorrSR['TL'] = ufloat(Ncorr_TL.n, 0.0 )
        datacorrSR['LT'] = ufloat(Ncorr_LT.n, 0.0 )
        datacorrSR['LL'] = ufloat(Ncorr_LL.n, 0.0 )

        # only consdier uncertainty from SB
        datacorrSB = {}
        datacorrSB['TT'] = ufloat( Ndata_TT_bothiso, 0.0)
        datacorrSB['TL'] = Ncorr_TL
        datacorrSB['LT'] = Ncorr_LT
        datacorrSB['LL'] = Ncorr_LL

        datacorr_nostat = {}
        datacorr_nostat['TT'] = ufloat( Ndata_TT_bothiso, 0.0 )
        datacorr_nostat['TL'] = ufloat( Ncorr_TL.n, 0.0 )
        datacorr_nostat['LT'] = ufloat( Ncorr_LT.n, 0.0 )
        datacorr_nostat['LL'] = ufloat( Ncorr_LL.n, 0.0 )

        results_stat_dataSR       = run_fit( datacorrSR       , eff_2d_nouncert)
        results_stat_dataSB       = run_fit( datacorrSB       , eff_2d_nouncert)
        results_stat_temp_tight = run_fit( datacorr_nostat, eff_results['stat_tight'] )
        results_stat_temp_loose = run_fit( datacorr_nostat, eff_results['stat_loose'] )
        results_stat_ff         = run_fit( datacorr_nostat, eff_results['stat_ff'] )
        results_syst_bkg        = run_fit( datacorr_nostat, eff_results['syst_bkg'] )
        results_syst_temp       = run_fit( datacorr_nostat, eff_results['syst_temp'] )


        text_results_stat_dataSR     = collect_results( results_stat_dataSR      , datacorr, eff_2d_nouncert  , templates_comb, eff_cuts, ndim)
        text_results_stat_dataSB     = collect_results( results_stat_dataSB      , datacorr, eff_2d_nouncert  , templates_comb, eff_cuts, ndim)
        text_results_stat_temp_tight = collect_results( results_stat_temp_tight, datacorr, eff_results['stat_tight'], templates_comb, eff_cuts, ndim)
        text_results_stat_temp_loose = collect_results( results_stat_temp_loose, datacorr, eff_results['stat_loose'], templates_comb, eff_cuts, ndim)
        text_results_stat_ff         = collect_results( results_stat_ff        , datacorr, eff_results['stat_ff'   ]     , templates_comb, eff_cuts, ndim)
        text_results_syst_bkg        = collect_results( results_syst_bkg       , datacorr, eff_results['syst_bkg']  , templates_comb, eff_cuts, ndim)
        text_results_syst_temp       = collect_results( results_syst_temp      , datacorr, eff_results['syst_temp'] , templates_comb, eff_cuts, ndim)

        
        print 'text_results_syst_bkg'
        print text_results_syst_bkg

        print 'Region = %s-%s' %( lead_reg, subl_reg)
        print 'Systematics = ', systematics
        print 'Lead pt range = ', lead_ptrange
        print 'Subl pt range = ', subl_ptrange

        print 'Npred_RR_TT = ', text_results_stat_dataSB['Npred_RR_TT']
        print 'Npred_RR_TL = ', text_results_stat_dataSB['Npred_RR_TL']
        print 'Npred_RF_TL = ', text_results_stat_dataSB['Npred_RF_TL']
        print 'Npred_FR_TL = ', text_results_stat_dataSB['Npred_FR_TL']
        print 'Npred_FF_TL = ', text_results_stat_dataSB['Npred_FF_TL']
        print 'Npred_RR_LT = ', text_results_stat_dataSB['Npred_RR_LT']
        print 'Npred_RF_LT = ', text_results_stat_dataSB['Npred_RF_LT']
        print 'Npred_FR_LT = ', text_results_stat_dataSB['Npred_FR_LT']
        print 'Npred_FF_LT = ', text_results_stat_dataSB['Npred_FF_LT']
        print 'Npred_RR_LL = ', text_results_stat_dataSB['Npred_RR_LL']
        print 'Npred_RF_LL = ', text_results_stat_dataSB['Npred_RF_LL']
        print 'Npred_FR_LL = ', text_results_stat_dataSB['Npred_FR_LL']
        print 'Npred_FF_LL = ', text_results_stat_dataSB['Npred_FF_LL']
        print '**************Background contributsion *******************'
        print 'Npred_RF_TT = ', text_results_stat_dataSB['Npred_RF_TT']
        print 'Npred_FR_TT = ', text_results_stat_dataSB['Npred_FR_TT']
        print 'Npred_FF_TT = ', text_results_stat_dataSB['Npred_FF_TT']
        print 'Sum = ', (text_results_stat_dataSB['Npred_RF_TT']+text_results_stat_dataSB['Npred_FR_TT']+text_results_stat_dataSB['Npred_FF_TT'])


        return text_results_stat_dataSR,text_results_stat_dataSB, text_results_stat_temp_tight, text_results_stat_temp_loose, text_results_stat_ff, text_results_syst_bkg, text_results_syst_temp


# depricated
#def run_generated_diphoton_fit( templates, lead_reg, subl_reg, n_data_gen, lead_ptrange=(None,None), subl_ptrange=(None,None), ndim=3, corr_factor=0.0, outputDir=None, outputPrefix='' ) :
#
#    rand = ROOT.TRandom3()
#    rand.SetSeed( int(time.mktime(time.localtime()) ) )
#
#    accept_reg = ['EB', 'EE']
#    if lead_reg not in accept_reg :
#        print 'Lead region does not make sense'
#        return
#    if subl_reg not in accept_reg :
#        print 'Subl region does not make sense'
#        return
#
#    # get the defaults
#    samples = get_default_samples()
#    plotbinning = get_default_binning()
#    cuts = get_default_cuts()
#
#    eff_cuts = {}
#    eff_cuts['lead'] = {}
#    eff_cuts['subl'] = {}
#    eff_cuts['lead']['tight'] = cuts[lead_reg]['tight']
#    eff_cuts['lead']['loose'] = cuts[lead_reg]['loose']
#    eff_cuts['subl']['tight'] = cuts[subl_reg]['tight']
#    eff_cuts['subl']['loose'] = cuts[subl_reg]['loose']
#
#    # get 2-d efficiencies from 1-d inputs
#    (eff_2d, eff_2d_syst_bkg, eff_2d_syst_temp) = generate_2d_efficiencies( templates, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange )
#
#    Ndata = {}
#    Ndata['TT'] = 0
#    Ndata['TL'] = 0
#    Ndata['LT'] = 0
#    Ndata['LL'] = 0
#    
#    eff_1d_lead_base = {}
#    eff_1d_subl_base = {}
#    eff_1d_lead_base['eff_F_T'] = eff_2d['eff_FF_TT'] + eff_2d['eff_FF_TL']
#    eff_1d_lead_base['eff_F_L'] = eff_2d['eff_FF_LL'] + eff_2d['eff_FF_LT']
#    eff_1d_subl_base['eff_F_T'] = eff_2d['eff_FF_TT'] + eff_2d['eff_FF_LT']
#    eff_1d_subl_base['eff_F_L'] = eff_2d['eff_FF_LL'] + eff_2d['eff_FF_TL']
#
#    # do FR
#    #for tag in ['FR', 'RF', 'FF'] :
#    for tag in ['FR', 'RF'] :
#        for i in xrange( 0, n_data_gen[tag] ) :
#
#            rndmval = rand.Rndm()
#
#            lead_tight = None
#            subl_tight = None
#
#            # 2d efficiencies are normalized to unity...just linearize the efficiencies to determine
#            # where the photons landed
#            if rndmval < (eff_2d['eff_%s_TT'%tag]) :
#                Ndata['TT'] = Ndata['TT']+1
#            elif rndmval < (eff_2d['eff_%s_TT'%tag] + eff_2d['eff_%s_TL'%tag]) :
#                Ndata['TL'] = Ndata['TL']+1
#            elif rndmval < (eff_2d['eff_%s_TT'%tag] + eff_2d['eff_%s_TL'%tag] + eff_2d['eff_%s_LT'%tag]) :
#                Ndata['LT'] = Ndata['LT']+1
#            elif rndmval < (eff_2d['eff_%s_TT'%tag] + eff_2d['eff_%s_TL'%tag] + eff_2d['eff_%s_LT'%tag] + eff_2d['eff_%s_LL'%tag]) :
#                Ndata['LL'] = Ndata['LL']+1
#            else :
#                print 'SHOULD NOT GET HERE -- templates not normalized to unity, it is ', (eff_2d['eff_%s_TT'%tag] + eff_2d['eff_%s_TL'%tag] + eff_2d['eff_%s_LT'%tag] + eff_2d['eff_%s_LL'%tag])
#
#    # do FF, allow for a correlation 
#    for i in xrange( 0, n_data_gen['FF'] ) :
#        # decide which photon to select first
#        lead_first = (rand.Rndm() < 0.5)
#        # generate random numbers for lead and subl
#        lead_rndm = rand.Rndm()
#        subl_rndm = rand.Rndm()
#
#        lead_tight = None
#        subl_tight = None
#        eff_1d_lead = {}
#        eff_1d_subl = {}
#        if lead_first :
#
#            #make sure efficiencies are normalized to unity
#            lead_norm = 1.0/(eff_1d_lead_base['eff_F_T']+eff_1d_lead_base['eff_F_L'])
#
#            eff_1d_lead['eff_F_T'] = lead_norm*eff_1d_lead_base['eff_F_T']
#            eff_1d_lead['eff_F_L'] = lead_norm*eff_1d_lead_base['eff_F_L']
#
#
#            # determine if the lead photon is loose or tight
#            # modify the subl efficiency based on the given correction factor
#            if lead_rndm < eff_1d_lead['eff_F_T'] : 
#                lead_tight = True
#                eff_1d_subl['eff_F_L'] = eff_1d_subl_base['eff_F_L']*(1-corr_factor)
#                eff_1d_subl['eff_F_T'] = eff_1d_subl_base['eff_F_T']
#            else :
#                lead_tight = False
#                eff_1d_subl['eff_F_L'] = eff_1d_subl_base['eff_F_L']*(1+corr_factor)
#                eff_1d_subl['eff_F_T'] = eff_1d_subl_base['eff_F_T']
#
#            # normalize the modified subl efficiencies
#            subl_norm = 1.0/(eff_1d_subl['eff_F_T']+eff_1d_subl['eff_F_L'])
#            eff_1d_subl['eff_F_T'] = subl_norm*eff_1d_subl['eff_F_T']
#            eff_1d_subl['eff_F_L'] = subl_norm*eff_1d_subl['eff_F_L']
#
#            # check if subl is loose or tight
#            if subl_rndm < eff_1d_subl['eff_F_T'] : 
#                subl_tight = True
#            else :
#                subl_tight = False
#
#        else :
#
#            #make sure efficiencies are normalized to unity
#            subl_norm = 1.0/(eff_1d_subl_base['eff_F_T']+eff_1d_subl_base['eff_F_L'])
#            eff_1d_subl['eff_F_T'] = subl_norm*eff_1d_subl_base['eff_F_T']
#            eff_1d_subl['eff_F_L'] = subl_norm*eff_1d_subl_base['eff_F_L']
#
#
#            # determine if the subl photon is loose or tight
#            # modify the lead efficiency based on the given correction factor
#            if subl_rndm < eff_1d_subl['eff_F_T'] : 
#                subl_tight = True
#                eff_1d_lead['eff_F_L'] = eff_1d_lead_base['eff_F_L']*(1-corr_factor)
#                eff_1d_lead['eff_F_T'] = eff_1d_lead_base['eff_F_T']
#            else :
#                subl_tight = False
#                eff_1d_lead['eff_F_L'] = eff_1d_lead_base['eff_F_L']*(1+corr_factor)
#                eff_1d_lead['eff_F_T'] = eff_1d_lead_base['eff_F_T']
#
#            # normalize the modified lead efficiencies
#            lead_norm = 1.0/(eff_1d_lead['eff_F_T']+eff_1d_lead['eff_F_L'])
#            eff_1d_lead['eff_F_T'] = lead_norm*eff_1d_lead['eff_F_T']
#            eff_1d_lead['eff_F_L'] = lead_norm*eff_1d_lead['eff_F_L']
#
#            # check if lead is loose or tight
#            if lead_rndm < eff_1d_lead['eff_F_T'] : 
#                lead_tight = True
#            else :
#                lead_tight = False
#
#        # make sure they were set
#        if lead_tight is None or subl_tight is None :
#            print 'Something went wrong!'
#            return
#
#        # fill the data
#        if lead_tight and subl_tight :
#            Ndata['TT'] = Ndata['TT']+1
#        elif lead_tight and not subl_tight :
#            Ndata['TL'] = Ndata['TL']+1
#        elif not lead_tight and subl_tight :
#            Ndata['LT'] = Ndata['LT']+1
#        else  :
#            Ndata['LL'] = Ndata['LL']+1
#
#    Ndata['TT'] = ufloat( Ndata['TT'], math.sqrt( Ndata['TT'] ) )
#    Ndata['TL'] = ufloat( Ndata['TL'], math.sqrt( Ndata['TL'] ) )
#    Ndata['LT'] = ufloat( Ndata['LT'], math.sqrt( Ndata['LT'] ) )
#    Ndata['LL'] = ufloat( Ndata['LL'], math.sqrt( Ndata['LL'] ) )
#
#    if ndim == 3 :
#        results = run_fit( {'TL': Ndata['TL'], 'LT' : Ndata['LT'], 'LL' : Ndata['LL']}, eff_2d )
#    if ndim == 4 :
#        results = run_fit( Ndata, eff_2d )
#
#
#    text_results=collections.OrderedDict()
#
#    for key, val in eff_2d.iteritems() :
#        text_results[key] = val
#
#    if ndim == 4 :
#
#        text_results['Ndata_TT'] = Ndata['TT']
#        text_results['Ndata_TL'] = Ndata['TL']
#        text_results['Ndata_LT'] = Ndata['LT']
#        text_results['Ndata_LL'] = Ndata['LL']
#
#        text_results['alpha_RR'] = results.item(0)
#        text_results['alpha_RF'] = results.item(1)
#        text_results['alpha_FR'] = results.item(2)
#        text_results['alpha_FF'] = results.item(3)
#
#        text_results['Npred_RR_TT'] = text_results['alpha_RR']*text_results['eff_RR_TT']
#        text_results['Npred_RR_TL'] = text_results['alpha_RR']*text_results['eff_RR_TL']
#        text_results['Npred_RR_LT'] = text_results['alpha_RR']*text_results['eff_RR_LT']
#        text_results['Npred_RR_LL'] = text_results['alpha_RR']*text_results['eff_RR_LL']
#
#    else :
#        text_results['Ndata_TT'] = ufloat(0, 0)
#        text_results['Ndata_TL'] = Ndata['TL']
#        text_results['Ndata_LT'] = Ndata['LT']
#        text_results['Ndata_LL'] = Ndata['LL']
#
#        text_results['alpha_RF'] = results.item(0)
#        text_results['alpha_FR'] = results.item(1)
#        text_results['alpha_FF'] = results.item(2)
#
#
#    text_results['Npred_RF_TT'] = text_results['alpha_RF']*text_results['eff_RF_TT']
#    text_results['Npred_RF_TL'] = text_results['alpha_RF']*text_results['eff_RF_TL']
#    text_results['Npred_RF_LT'] = text_results['alpha_RF']*text_results['eff_RF_LT']
#    text_results['Npred_RF_LL'] = text_results['alpha_RF']*text_results['eff_RF_LL']
#
#    text_results['Npred_FR_TT'] = text_results['alpha_FR']*text_results['eff_FR_TT']
#    text_results['Npred_FR_TL'] = text_results['alpha_FR']*text_results['eff_FR_TL']
#    text_results['Npred_FR_LT'] = text_results['alpha_FR']*text_results['eff_FR_LT']
#    text_results['Npred_FR_LL'] = text_results['alpha_FR']*text_results['eff_FR_LL']
#
#    text_results['Npred_FF_TT'] = text_results['alpha_FF']*text_results['eff_FF_TT']
#    text_results['Npred_FF_TL'] = text_results['alpha_FF']*text_results['eff_FF_TL']
#    text_results['Npred_FF_LT'] = text_results['alpha_FF']*text_results['eff_FF_LT']
#    text_results['Npred_FF_LL'] = text_results['alpha_FF']*text_results['eff_FF_LL']
#
#    text_results['Closure_TT'] = ( (text_results['Npred_RF_TT'] +text_results['Npred_FR_TT'] +text_results['Npred_FF_TT'] ) - Ndata['TT'] ) / Ndata['TT']
#    text_results['Closure_TL'] = ( (text_results['Npred_RF_TL'] +text_results['Npred_FR_TL'] +text_results['Npred_FF_TL'] ) - Ndata['TL'] ) / Ndata['TL']
#    text_results['Closure_LT'] = ( (text_results['Npred_RF_LT'] +text_results['Npred_FR_LT'] +text_results['Npred_FF_LT'] ) - Ndata['LT'] ) / Ndata['LT']
#    text_results['Closure_LL'] = ( (text_results['Npred_RF_LL'] +text_results['Npred_FR_LL'] +text_results['Npred_FF_LL'] ) - Ndata['LL'] ) / Ndata['LL']


def run_diphoton_fit( templates, gg_hist, lead_reg, subl_reg, templates_corr=None, lead_ptrange=(None,None), subl_ptrange=(None,None), ndim=3, outputDir=None, outputPrefix='', systematics=None, fitvar=None) :

    accept_reg = ['EB', 'EE']
    if lead_reg not in accept_reg :
        print 'Lead region does not make sense'
        return
    if subl_reg not in accept_reg :
        print 'Subl region does not make sense'
        return

    print 'Region = %s-%s', (lead_reg, subl_reg)
    print 'Lead Pt range = ', lead_ptrange
    print 'Subl Pt range = ', subl_ptrange
    # get the defaults
    samples = get_default_samples()
    plotbinning = get_default_binning(fitvar)
    cuts = get_default_cuts(fitvar)

    # Find the bins corresponding to the cuts
    # lead photon on X axis, subl on Y axis
    if isinstance( gg_hist, dict ) :
        bins_subl_tight = ( gg_hist['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['tight'][0] ), gg_hist['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['tight'][1] ) )
        bins_subl_loose = ( gg_hist['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['loose'][0] ), gg_hist['leadPass'].GetXaxis().FindBin( cuts[subl_reg]['loose'][1] ) )

        print 'bins_subl_tight ', bins_subl_tight
        print 'bins_subl_loose ', bins_subl_loose


        # Integrate to the the data in the four regions
        Ndata_TT = gg_hist['leadPass'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL = gg_hist['leadPass'].Integral( bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT = gg_hist['leadFail'].Integral( bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL = gg_hist['leadFail'].Integral( bins_subl_loose[0], bins_subl_loose[1] )

    else :

        bins_lead_tight = ( gg_hist.GetXaxis().FindBin( cuts[lead_reg]['tight'][0] ), gg_hist.GetXaxis().FindBin( cuts[lead_reg]['tight'][1] ) )
        bins_lead_loose = ( gg_hist.GetXaxis().FindBin( cuts[lead_reg]['loose'][0] ), gg_hist.GetXaxis().FindBin( cuts[lead_reg]['loose'][1] ) )
        bins_subl_tight = ( gg_hist.GetYaxis().FindBin( cuts[subl_reg]['tight'][0] ), gg_hist.GetYaxis().FindBin( cuts[subl_reg]['tight'][1] ) )
        bins_subl_loose = ( gg_hist.GetYaxis().FindBin( cuts[subl_reg]['loose'][0] ), gg_hist.GetYaxis().FindBin( cuts[subl_reg]['loose'][1] ) )

        print 'bins_lead_tight ', bins_lead_tight
        print 'bins_lead_loose ', bins_lead_loose
        print 'bins_subl_tight ', bins_subl_tight
        print 'bins_subl_loose ', bins_subl_loose

        # Integrate to the the data in the four regions
        Ndata_TT = gg_hist.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_TL = gg_hist.Integral( bins_lead_tight[0], bins_lead_tight[1], bins_subl_loose[0], bins_subl_loose[1] )
        Ndata_LT = gg_hist.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_tight[0], bins_subl_tight[1] )
        Ndata_LL = gg_hist.Integral( bins_lead_loose[0], bins_lead_loose[1], bins_subl_loose[0], bins_subl_loose[1] )

    # ufloat it!
    Ndata = {}
    Ndata['TT'] = ufloat( Ndata_TT, math.sqrt(Ndata_TT ), 'Ndata_TT' )
    Ndata['TL'] = ufloat( Ndata_TL, math.sqrt(Ndata_TL ), 'Ndata_TL' )
    Ndata['LT'] = ufloat( Ndata_LT, math.sqrt(Ndata_LT ), 'Ndata_LT' )
    Ndata['LL'] = ufloat( Ndata_LL, math.sqrt(Ndata_LL ), 'Ndata_LL' )

    print 'N data TT = ', Ndata['TT']
    print 'N data TL = ', Ndata['TL']
    print 'N data LT = ', Ndata['LT']
    print 'N data LL = ', Ndata['LL']

    # arragnge the cuts by 
    eff_cuts = {}
    eff_cuts['lead'] = {}
    eff_cuts['subl'] = {}
    eff_cuts['lead']['tight'] = cuts[lead_reg]['tight']
    eff_cuts['lead']['loose'] = cuts[lead_reg]['loose']
    eff_cuts['subl']['tight'] = cuts[subl_reg]['tight']
    eff_cuts['subl']['loose'] = cuts[subl_reg]['loose']

    # get 2-d efficiencies from 1-d inputs
    eff_results = generate_2d_efficiencies( templates, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar, systematics=systematics )
    (eff_1d_stat_tight, eff_1d_stat_loose, eff_1d_syst_bkg, eff_1d_syst_temp) =generate_1d_efficiencies( templates, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar, systematics=systematics )

    if templates_corr is not None :
        eff_ff_2d_stat, eff_ff_2d_syst = generate_2d_corr_efficiencies( templates_corr, eff_cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=fitvar )

        # for correlated FF templates
        # the uncertainties from 1-d templates
        # don't apply.  Set those to zero
        eff_results['stat_tight']['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['stat_tight']['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['stat_loose']['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['syst_bkg'  ]['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_TT'] = ufloat( eff_ff_2d_stat['eff_FF_TT'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_TL'] = ufloat( eff_ff_2d_stat['eff_FF_TL'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_LT'] = ufloat( eff_ff_2d_stat['eff_FF_LT'].n, 0.0 )
        eff_results['syst_temp' ]['eff_FF_LL'] = ufloat( eff_ff_2d_stat['eff_FF_LL'].n, 0.0 )

        # make a new uncertainty
        # with fake-fake uncertainties
        eff_results['stat_ff'] = {}
        eff_results['stat_ff']['eff_FF_TT'] = eff_ff_2d_stat['eff_FF_TT']
        eff_results['stat_ff']['eff_FF_TL'] = eff_ff_2d_stat['eff_FF_TL']
        eff_results['stat_ff']['eff_FF_LT'] = eff_ff_2d_stat['eff_FF_LT']
        eff_results['stat_ff']['eff_FF_LL'] = eff_ff_2d_stat['eff_FF_LL']

        # put in all of the other values, use stat_tight as template
        eff_results['stat_ff']['eff_RR_TT'] = ufloat( eff_results['stat_tight']['eff_RR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_TL'] = ufloat( eff_results['stat_tight']['eff_RR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LT'] = ufloat( eff_results['stat_tight']['eff_RR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LL'] = ufloat( eff_results['stat_tight']['eff_RR_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_RF_TT'] = ufloat( eff_results['stat_tight']['eff_RF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_TL'] = ufloat( eff_results['stat_tight']['eff_RF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LT'] = ufloat( eff_results['stat_tight']['eff_RF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LL'] = ufloat( eff_results['stat_tight']['eff_RF_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_FR_TT'] = ufloat( eff_results['stat_tight']['eff_FR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_TL'] = ufloat( eff_results['stat_tight']['eff_FR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LT'] = ufloat( eff_results['stat_tight']['eff_FR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LL'] = ufloat( eff_results['stat_tight']['eff_FR_LL'].n, 0.0 )
    else :
        # put in all of the other values, use stat_tight as template
        eff_results['stat_ff'] = {}
        eff_results['stat_ff']['eff_FF_TT'] = ufloat( eff_results['stat_tight']['eff_FF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_TL'] = ufloat( eff_results['stat_tight']['eff_FF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_LT'] = ufloat( eff_results['stat_tight']['eff_FF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FF_LL'] = ufloat( eff_results['stat_tight']['eff_FF_LL'].n, 0.0 )

        eff_results['stat_ff']['eff_RR_TT'] = ufloat( eff_results['stat_tight']['eff_RR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_TL'] = ufloat( eff_results['stat_tight']['eff_RR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LT'] = ufloat( eff_results['stat_tight']['eff_RR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RR_LL'] = ufloat( eff_results['stat_tight']['eff_RR_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_RF_TT'] = ufloat( eff_results['stat_tight']['eff_RF_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_TL'] = ufloat( eff_results['stat_tight']['eff_RF_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LT'] = ufloat( eff_results['stat_tight']['eff_RF_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_RF_LL'] = ufloat( eff_results['stat_tight']['eff_RF_LL'].n, 0.0 )
        
        eff_results['stat_ff']['eff_FR_TT'] = ufloat( eff_results['stat_tight']['eff_FR_TT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_TL'] = ufloat( eff_results['stat_tight']['eff_FR_TL'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LT'] = ufloat( eff_results['stat_tight']['eff_FR_LT'].n, 0.0 )
        eff_results['stat_ff']['eff_FR_LL'] = ufloat( eff_results['stat_tight']['eff_FR_LL'].n, 0.0 )

        


    eff_2d_nouncert = {}
    for key, val in eff_results['stat_tight'].iteritems() :
        if type( val ) == type( ufloat(0,0) ) :
            eff_2d_nouncert[key] = ufloat( val.n, 0.0 )
        else :
            eff_2d_nouncert[key] = val

    if ndim == 3 :

        data = {'TL': Ndata['TL'], 'LT' : Ndata['LT'], 'LL' : Ndata['LL']}
        data_nostat = { }
        data_nostat['TL'] = ufloat( Ndata['TL'].n, 0.0 )
        data_nostat['LT'] = ufloat( Ndata['LT'].n, 0.0 )
        data_nostat['LL'] = ufloat( Ndata['LL'].n, 0.0 )

        results_stat_data       = run_fit( data       , eff_2d_nouncert)
        results_stat_temp_tight = run_fit( data_nostat, eff_results['stat_tight'] )
        results_stat_temp_loose = run_fit( data_nostat, eff_results['stat_loose'] )
        results_stat_ff         = run_fit( data_nostat, eff_results['stat_ff'] )
        results_syst_bkg        = run_fit( data_nostat, eff_results['syst_bkg'] )
        results_syst_temp       = run_fit( data_nostat, eff_results['syst_temp'] )

    if ndim == 4 :
        print 'RUNNING FIT WITH 4 DIM'
        # consider only SB uncertainties
        data_SB = { }
        data_SB['TT'] = ufloat( Ndata['TT'].n, 0.0 )
        data_SB['TL'] = Ndata['TL']
        data_SB['LT'] = Ndata['LT']
        data_SB['LL'] = Ndata['LL']

        # consider only SR uncertainties
        data_SR = { }
        data_SR['TT'] =  Ndata['TT']
        data_SR['TL'] = ufloat( Ndata['TL'].n, 0.0 )
        data_SR['LT'] = ufloat( Ndata['LT'].n, 0.0 )
        data_SR['LL'] = ufloat( Ndata['LL'].n, 0.0 )

        # no data uncertainties
        data_nostat = { }
        data_nostat['TT'] = ufloat( Ndata['TT'].n, 0.0 )
        data_nostat['TL'] = ufloat( Ndata['TL'].n, 0.0 )
        data_nostat['LT'] = ufloat( Ndata['LT'].n, 0.0 )
        data_nostat['LL'] = ufloat( Ndata['LL'].n, 0.0 )

        results_stat_dataSB     = run_fit( data_SB, eff_2d_nouncert)
        results_stat_dataSR     = run_fit( data_SR, eff_2d_nouncert)
        results_stat_temp_tight = run_fit( data_nostat, eff_results['stat_tight'] )
        results_stat_temp_loose = run_fit( data_nostat, eff_results['stat_loose'] )
        results_stat_ff         = run_fit( data_nostat, eff_results['stat_ff'] )
        results_syst_bkg        = run_fit( data_nostat, eff_results['syst_bkg'] )
        results_syst_temp       = run_fit( data_nostat, eff_results['syst_temp'] )

    if ndim == 3 :
        idxrf = 0
        idxfr = 1
        idxff = 2

    if ndim == 4 :
        idxrf = 1
        idxfr = 2
        idxff = 3

    #save_normalized_template_hists( gg_hist, results, templates, eff_2d, bins_lead_loose, bins_subl_loose, ndim, lead_ptrange=lead_ptrange, subl_ptrange=subl_ptrange, outputDir=outputDir )

    #get fitted predictions
    if ndim == 3 :
         p_RR_TT = ufloat(1.0, 0.0 )
         p_RR_TL = ufloat(0.0, 0.0 )
         p_RR_LT = ufloat(0.0, 0.0 )
         p_RR_LL = ufloat(0.0, 0.0 )
         p_RF_TT = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RF_TT']
         p_RF_TL = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RF_TL']
         p_RF_LT = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RF_LT']
         p_RF_LL = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RF_LL']
         p_FR_TT = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_FR_TT']
         p_FR_TL = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_FR_TL']
         p_FR_LT = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_FR_LT']
         p_FR_LL = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_FR_LL']
         p_FF_TT = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FF_TT']
         p_FF_TL = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FF_TL']
         p_FF_LT = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FF_LT']
         p_FF_LL = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FF_LL']
    if ndim == 4 : #everybody moves down 1 if 4 dim
         p_RR_TT = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RR_TT']
         p_RR_TL = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RR_TL']
         p_RR_LT = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RR_LT']
         p_RR_LL = results_stat_dataSB.item(0)*eff_results['stat_tight']['eff_RR_LL']
         p_RF_TT = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_RF_TT']
         p_RF_TL = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_RF_TL']
         p_RF_LT = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_RF_LT']
         p_RF_LL = results_stat_dataSB.item(1)*eff_results['stat_tight']['eff_RF_LL']
         p_FR_TT = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FR_TT']
         p_FR_TL = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FR_TL']
         p_FR_LT = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FR_LT']
         p_FR_LL = results_stat_dataSB.item(2)*eff_results['stat_tight']['eff_FR_LL']
         p_FF_TT = results_stat_dataSB.item(3)*eff_results['stat_tight']['eff_FF_TT']
         p_FF_TL = results_stat_dataSB.item(3)*eff_results['stat_tight']['eff_FF_TL']
         p_FF_LT = results_stat_dataSB.item(3)*eff_results['stat_tight']['eff_FF_LT']
         p_FF_LL = results_stat_dataSB.item(3)*eff_results['stat_tight']['eff_FF_LL']

    print 'Npred FF_LL'
    print p_FF_LL
    print 'Npred FF_LT'
    print p_FF_LT
    print 'Npred FF_TL'
    print p_FF_TL
    print 'Npred FF_TT'
    print p_FF_TT

    print 'Npred RF_LL'
    print p_RF_LL
    print 'Npred RF_LT'
    print p_RF_LT
    print 'Npred RF_TL'
    print p_RF_TL
    print 'Npred RF_TT'
    print p_RF_TT

    print 'Npred FR_LL'
    print p_FR_LL
    print 'Npred FR_LT'
    print p_FR_LT
    print 'Npred FR_TL'
    print p_FR_TL
    print 'Npred FR_TT'
    print p_FR_TT

    print 'Npred RR_LL'
    print p_RR_LL
    print 'Npred RR_LT'
    print p_RR_LT
    print 'Npred RR_TL'
    print p_RR_TL
    print 'Npred RR_TT'
    print p_RR_TT

    print 'Npred Bkg Total' 
    print (p_FF_TT+p_RF_TT+p_FR_TT)

    # make normalized template histograms
    # look at the leading photon distribution (X) while sublead is loose
    if not isinstance( gg_hist, dict ) :
        gg_hist_proj_lead_subl_tight = gg_hist.ProjectionX( 'gg_hist_proj_lead_subl_tight', bins_subl_tight[0], bins_subl_tight[1] )
        gg_hist_proj_subl_lead_tight = gg_hist.ProjectionY( 'gg_hist_proj_subl_lead_tight', bins_lead_tight[0], bins_lead_tight[1] )
        gg_hist_proj_lead_subl_loose = gg_hist.ProjectionX( 'gg_hist_proj_lead_subl_loose', bins_subl_loose[0], bins_subl_loose[1] )
        gg_hist_proj_subl_lead_loose = gg_hist.ProjectionY( 'gg_hist_proj_subl_lead_loose', bins_lead_loose[0], bins_lead_loose[1] )

        gg_hist_proj_lead = gg_hist.ProjectionX( 'gg_hist_proj_lead')
        gg_hist_proj_subl = gg_hist.ProjectionY( 'gg_hist_proj_subl')

        hist_temp_rr_subl_loose = templates['lead']['real']['Data'].Clone( 'hist_temp_rr_subl_loose' )
        hist_temp_rr_subl_tight = templates['lead']['real']['Data'].Clone( 'hist_temp_rr_subl_tight' )

        hist_temp_rf_subl_loose = templates['lead']['real']['Data'].Clone( 'hist_temp_rf_subl_loose' )
        hist_temp_rf_subl_tight = templates['lead']['real']['Data'].Clone( 'hist_temp_rf_subl_tight' )

        hist_temp_fr_subl_loose = templates['lead']['fake']['Data'].Clone( 'hist_temp_fr_subl_loose' )
        hist_temp_fr_subl_tight = templates['lead']['fake']['Data'].Clone( 'hist_temp_fr_subl_tight' )

        hist_temp_ff_subl_loose = templates['lead']['fake']['Data'].Clone( 'hist_temp_ff_subl_loose' )
        hist_temp_ff_subl_tight = templates['lead']['fake']['Data'].Clone( 'hist_temp_ff_subl_tight' )

        hist_temp_rr_lead_loose = templates['subl']['real']['Data'].Clone( 'hist_temp_rr_lead_loose' )
        hist_temp_rr_lead_tight = templates['subl']['real']['Data'].Clone( 'hist_temp_rr_lead_tight' )

        hist_temp_rf_lead_loose = templates['subl']['fake']['Data'].Clone( 'hist_temp_rf_lead_loose' )
        hist_temp_rf_lead_tight = templates['subl']['fake']['Data'].Clone( 'hist_temp_rf_lead_tight' )

        hist_temp_fr_lead_loose = templates['subl']['real']['Data'].Clone( 'hist_temp_fr_lead_loose' )
        hist_temp_fr_lead_tight = templates['subl']['real']['Data'].Clone( 'hist_temp_fr_lead_tight' )

        hist_temp_ff_lead_loose = templates['subl']['fake']['Data'].Clone( 'hist_temp_ff_lead_loose' )
        hist_temp_ff_lead_tight = templates['subl']['fake']['Data'].Clone( 'hist_temp_ff_lead_tight' )

        if templates['lead']['real']['Background'] is not None :
            hist_temp_rr_subl_loose.Add( templates['lead']['real']['Background'] )
            hist_temp_rr_subl_tight.Add( templates['lead']['real']['Background'] )
            hist_temp_rf_subl_loose.Add( templates['lead']['real']['Background'] )
            hist_temp_rf_subl_tight.Add( templates['lead']['real']['Background'] )
        if templates['lead']['fake']['Background'] is not None :
            hist_temp_fr_subl_loose.Add( templates['lead']['fake']['Background'] )
            hist_temp_fr_subl_tight.Add( templates['lead']['fake']['Background'] )
            hist_temp_ff_subl_loose.Add( templates['lead']['fake']['Background'] )
            hist_temp_ff_subl_tight.Add( templates['lead']['fake']['Background'] )
        if templates['subl']['real']['Background'] is not None :
            hist_temp_rr_lead_loose.Add( templates['subl']['real']['Background'] )
            hist_temp_rr_lead_tight.Add( templates['subl']['real']['Background'] )
            hist_temp_fr_lead_loose.Add( templates['subl']['real']['Background'] )
            hist_temp_fr_lead_tight.Add( templates['subl']['real']['Background'] )
        if templates['subl']['fake']['Background'] is not None :
            hist_temp_rf_lead_loose.Add( templates['subl']['fake']['Background'] )
            hist_temp_rf_lead_tight.Add( templates['subl']['fake']['Background'] )
            hist_temp_ff_lead_loose.Add( templates['subl']['fake']['Background'] )
            hist_temp_ff_lead_tight.Add( templates['subl']['fake']['Background'] )

        #normalize lead real template according to fit
        hist_temp_rr_subl_loose.Scale( (p_RR_TL+p_RR_LL).n /hist_temp_rr_subl_loose.Integral() )
        hist_temp_rr_subl_tight.Scale( (p_RR_TT+p_RR_LT).n /hist_temp_rr_subl_tight.Integral() )

        hist_temp_rf_subl_loose.Scale( (p_RF_TL+p_RF_LL).n /hist_temp_rf_subl_loose.Integral() )
        hist_temp_rf_subl_tight.Scale( (p_RF_TT+p_RF_LT).n /hist_temp_rf_subl_tight.Integral() )

        hist_temp_fr_subl_loose.Scale( (p_FR_TL+p_FR_LL).n /hist_temp_fr_subl_loose.Integral() )
        hist_temp_fr_subl_tight.Scale( (p_FR_TT+p_FR_LT).n /hist_temp_fr_subl_tight.Integral() )

        hist_temp_ff_subl_loose.Scale( (p_FF_TL+p_FF_LL).n /hist_temp_ff_subl_loose.Integral() )
        hist_temp_ff_subl_tight.Scale( (p_FF_TT+p_FF_LT).n /hist_temp_ff_subl_tight.Integral() )

        hist_temp_rr_lead_loose.Scale( (p_RR_LT+p_RR_LL).n /hist_temp_rr_lead_loose.Integral() )
        hist_temp_rr_lead_tight.Scale( (p_RR_TT+p_RR_TL).n /hist_temp_rr_lead_tight.Integral() )

        hist_temp_rf_lead_loose.Scale( (p_RF_LT+p_RF_LL).n /hist_temp_rf_lead_loose.Integral() )
        hist_temp_rf_lead_tight.Scale( (p_RF_TT+p_RF_TL).n /hist_temp_rf_lead_tight.Integral() )

        hist_temp_fr_lead_loose.Scale( (p_FR_LT+p_FR_LL).n /hist_temp_fr_lead_loose.Integral() )
        hist_temp_fr_lead_tight.Scale( (p_FR_TT+p_FR_TL).n /hist_temp_fr_lead_tight.Integral() )

        hist_temp_ff_lead_loose.Scale( (p_FF_LT+p_FF_LL).n /hist_temp_ff_lead_loose.Integral() )
        hist_temp_ff_lead_tight.Scale( (p_FF_TT+p_FF_TL).n /hist_temp_ff_lead_tight.Integral() )

        hist_temp_rr_proj_lead = hist_temp_rr_subl_loose.Clone( 'hist_temp_rr_proj_lead' )
        hist_temp_rr_proj_lead.Add(hist_temp_rr_subl_tight )
        hist_temp_rr_proj_subl = hist_temp_rr_lead_loose.Clone( 'hist_temp_rr_proj_subl' )
        hist_temp_rr_proj_subl.Add(hist_temp_rr_lead_tight )

        hist_temp_rf_proj_lead = hist_temp_rf_subl_loose.Clone( 'hist_temp_rf_proj_lead' )
        hist_temp_rf_proj_lead.Add(hist_temp_rf_subl_tight )
        hist_temp_rf_proj_subl = hist_temp_rf_lead_loose.Clone( 'hist_temp_rf_proj_subl' )
        hist_temp_rf_proj_subl.Add(hist_temp_rf_lead_tight )

        hist_temp_fr_proj_lead = hist_temp_fr_subl_loose.Clone( 'hist_temp_fr_proj_lead' )
        hist_temp_fr_proj_lead.Add(hist_temp_fr_subl_tight )
        hist_temp_fr_proj_subl = hist_temp_fr_lead_loose.Clone( 'hist_temp_fr_proj_subl' )
        hist_temp_fr_proj_subl.Add(hist_temp_fr_lead_tight )

        hist_temp_ff_proj_lead = hist_temp_ff_subl_loose.Clone( 'hist_temp_ff_proj_lead' )
        hist_temp_ff_proj_lead.Add(hist_temp_ff_subl_tight )
        hist_temp_ff_proj_subl = hist_temp_ff_lead_loose.Clone( 'hist_temp_ff_proj_subl' )
        hist_temp_ff_proj_subl.Add(hist_temp_ff_lead_tight )

        if fitvar == 'chIsoCorr' :

            binwidth_eb = (plotbinning['EB'][2]-plotbinning['EB'][1])/float(plotbinning['EB'][0])
            binwidth_ee = (plotbinning['EE'][2]-plotbinning['EE'][1])/float(plotbinning['EE'][0])

            varbin = {} 
            varbin['EB'] = [plotbinning['EB'][1], plotbinning['EB'][1]+binwidth_eb, plotbinning['EB'][2] ]
            varbin['EE'] = [plotbinning['EE'][1], plotbinning['EE'][1]+binwidth_ee, plotbinning['EE'][2] ]


            gg_hist_proj_lead_subl_tight = sampManData.do_variable_rebinning( gg_hist_proj_lead_subl_tight, varbin[lead_reg] )
            gg_hist_proj_lead_subl_loose = sampManData.do_variable_rebinning( gg_hist_proj_lead_subl_loose, varbin[lead_reg] )
            hist_temp_ff_subl_loose = sampManData.do_variable_rebinning( hist_temp_ff_subl_loose, varbin[lead_reg] )
            hist_temp_ff_subl_tight = sampManData.do_variable_rebinning( hist_temp_ff_subl_tight, varbin[lead_reg] )
            hist_temp_fr_subl_loose = sampManData.do_variable_rebinning( hist_temp_fr_subl_loose, varbin[lead_reg] )
            hist_temp_fr_subl_tight = sampManData.do_variable_rebinning( hist_temp_fr_subl_tight, varbin[lead_reg] )
            hist_temp_rf_subl_loose = sampManData.do_variable_rebinning( hist_temp_rf_subl_loose, varbin[lead_reg] )
            hist_temp_rf_subl_tight = sampManData.do_variable_rebinning( hist_temp_rf_subl_tight, varbin[lead_reg] )
            hist_temp_rr_subl_loose = sampManData.do_variable_rebinning( hist_temp_rr_subl_loose, varbin[lead_reg] )
            hist_temp_rr_subl_tight = sampManData.do_variable_rebinning( hist_temp_rr_subl_tight, varbin[lead_reg] )
            hist_temp_ff_proj_lead  = sampManData.do_variable_rebinning( hist_temp_ff_proj_lead , varbin[lead_reg] )
            hist_temp_fr_proj_lead  = sampManData.do_variable_rebinning( hist_temp_fr_proj_lead , varbin[lead_reg] )
            hist_temp_rf_proj_lead  = sampManData.do_variable_rebinning( hist_temp_rf_proj_lead , varbin[lead_reg] )
            hist_temp_rr_proj_lead  = sampManData.do_variable_rebinning( hist_temp_rr_proj_lead , varbin[lead_reg] )

            gg_hist_proj_subl_lead_tight = sampManData.do_variable_rebinning( gg_hist_proj_subl_lead_tight, varbin[subl_reg] )
            gg_hist_proj_subl_lead_loose = sampManData.do_variable_rebinning( gg_hist_proj_subl_lead_loose, varbin[subl_reg] )
            hist_temp_ff_lead_loose = sampManData.do_variable_rebinning( hist_temp_ff_lead_loose, varbin[subl_reg] )
            hist_temp_ff_lead_tight = sampManData.do_variable_rebinning( hist_temp_ff_lead_tight, varbin[subl_reg] )
            hist_temp_rf_lead_loose = sampManData.do_variable_rebinning( hist_temp_rf_lead_loose, varbin[subl_reg] )
            hist_temp_rf_lead_tight = sampManData.do_variable_rebinning( hist_temp_rf_lead_tight, varbin[subl_reg] )
            hist_temp_fr_lead_loose = sampManData.do_variable_rebinning( hist_temp_fr_lead_loose, varbin[subl_reg] )
            hist_temp_fr_lead_tight = sampManData.do_variable_rebinning( hist_temp_fr_lead_tight, varbin[subl_reg] )
            hist_temp_rr_lead_loose = sampManData.do_variable_rebinning( hist_temp_rr_lead_loose, varbin[subl_reg] )
            hist_temp_rr_lead_tight = sampManData.do_variable_rebinning( hist_temp_rr_lead_tight, varbin[subl_reg] )
            hist_temp_ff_proj_subl  = sampManData.do_variable_rebinning( hist_temp_ff_proj_subl , varbin[subl_reg] )
            hist_temp_fr_proj_subl  = sampManData.do_variable_rebinning( hist_temp_fr_proj_subl , varbin[subl_reg] )
            hist_temp_rf_proj_subl  = sampManData.do_variable_rebinning( hist_temp_rf_proj_subl , varbin[subl_reg] )
            hist_temp_rr_proj_subl  = sampManData.do_variable_rebinning( hist_temp_rr_proj_subl , varbin[subl_reg] )

        gg_hist_proj_subl_lead_tight.SetMarkerSize(1.1)
        gg_hist_proj_subl_lead_tight.SetMarkerStyle(21)
        gg_hist_proj_subl_lead_tight.SetMarkerColor(ROOT.kBlack)
        gg_hist_proj_subl_lead_loose.SetMarkerSize(1.1)
        gg_hist_proj_subl_lead_loose.SetMarkerStyle(21)
        gg_hist_proj_subl_lead_loose.SetMarkerColor(ROOT.kBlack)

        gg_hist_proj_lead_subl_tight.SetMarkerSize(1.1)
        gg_hist_proj_lead_subl_tight.SetMarkerStyle(21)
        gg_hist_proj_lead_subl_tight.SetMarkerColor(ROOT.kBlack)
        gg_hist_proj_lead_subl_loose.SetMarkerSize(1.1)
        gg_hist_proj_lead_subl_loose.SetMarkerStyle(21)
        gg_hist_proj_lead_subl_loose.SetMarkerColor(ROOT.kBlack)

        format_hist( hist_temp_rr_subl_loose, ROOT.kGreen )
        format_hist( hist_temp_rr_subl_tight, ROOT.kGreen )
        format_hist( hist_temp_rr_lead_loose, ROOT.kGreen )
        format_hist( hist_temp_rr_lead_tight, ROOT.kGreen )
        format_hist( hist_temp_rr_proj_subl , ROOT.kGreen )
        format_hist( hist_temp_rr_proj_lead , ROOT.kGreen )

        format_hist( hist_temp_rf_subl_loose, ROOT.kMagenta )
        format_hist( hist_temp_rf_subl_tight, ROOT.kMagenta )
        format_hist( hist_temp_rf_lead_loose, ROOT.kMagenta )
        format_hist( hist_temp_rf_lead_tight, ROOT.kMagenta )
        format_hist( hist_temp_rf_proj_subl , ROOT.kMagenta )
        format_hist( hist_temp_rf_proj_lead , ROOT.kMagenta )

        format_hist( hist_temp_fr_subl_loose, ROOT.kCyan )
        format_hist( hist_temp_fr_subl_tight, ROOT.kCyan )
        format_hist( hist_temp_fr_lead_loose, ROOT.kCyan )
        format_hist( hist_temp_fr_lead_tight, ROOT.kCyan )
        format_hist( hist_temp_fr_proj_subl , ROOT.kCyan )
        format_hist( hist_temp_fr_proj_lead , ROOT.kCyan )

        format_hist( hist_temp_ff_subl_loose, ROOT.kRed )
        format_hist( hist_temp_ff_subl_tight, ROOT.kRed )
        format_hist( hist_temp_ff_lead_loose, ROOT.kRed )
        format_hist( hist_temp_ff_lead_tight, ROOT.kRed )
        format_hist( hist_temp_ff_proj_subl , ROOT.kRed )
        format_hist( hist_temp_ff_proj_lead , ROOT.kRed )

        

        if lead_reg == 'EE' and gg_hist_proj_lead_subl_tight.GetNbinsX() > 100  :
            gg_hist_proj_lead_subl_tight.Rebin(10)
            gg_hist_proj_lead_subl_loose.Rebin(10)
            hist_temp_ff_subl_loose.Rebin(10)
            hist_temp_ff_subl_tight.Rebin(10)
            hist_temp_fr_subl_loose.Rebin(10)
            hist_temp_fr_subl_tight.Rebin(10)
            hist_temp_rf_subl_loose.Rebin(10)
            hist_temp_rf_subl_tight.Rebin(10)
            hist_temp_rr_subl_loose.Rebin(10)
            hist_temp_rr_subl_tight.Rebin(10)

            hist_temp_ff_proj_lead .Rebin(10)
            hist_temp_fr_proj_lead .Rebin(10)
            hist_temp_rf_proj_lead .Rebin(10)
            hist_temp_rr_proj_lead .Rebin(10)

        if subl_reg == 'EE' and gg_hist_proj_subl_lead_tight.GetNbinsX() > 100 :
            gg_hist_proj_subl_lead_tight.Rebin(10)
            gg_hist_proj_subl_lead_loose.Rebin(10)
            hist_temp_ff_lead_loose.Rebin(10)
            hist_temp_ff_lead_tight.Rebin(10)
            hist_temp_rf_lead_loose.Rebin(10)
            hist_temp_rf_lead_tight.Rebin(10)
            hist_temp_fr_lead_loose.Rebin(10)
            hist_temp_fr_lead_tight.Rebin(10)
            hist_temp_rr_lead_loose.Rebin(10)
            hist_temp_rr_lead_tight.Rebin(10)

            hist_temp_ff_proj_subl .Rebin(10)
            hist_temp_fr_proj_subl .Rebin(10)
            hist_temp_rf_proj_subl .Rebin(10)
            hist_temp_rr_proj_subl .Rebin(10)

        #can_proj_lead_subl_loose = ROOT.TCanvas('proj_lead_subl_loose', '')
        #can_proj_lead_subl_tight = ROOT.TCanvas('proj_lead_subl_tight', '')
        #can_proj_subl_lead_loose = ROOT.TCanvas('proj_subl_lead_loose', '')
        #can_proj_subl_lead_tight = ROOT.TCanvas('proj_subl_lead_tight', '')
        #can_proj_lead = ROOT.TCanvas('proj_lead', '')
        #can_proj_subl = ROOT.TCanvas('proj_subl', '')

        can_proj_lead_subl_loose = ROOT.TCanvas(str(uuid.uuid4()), '')
        can_proj_lead_subl_tight = ROOT.TCanvas(str(uuid.uuid4()), '')
        can_proj_subl_lead_loose = ROOT.TCanvas(str(uuid.uuid4()), '')
        can_proj_subl_lead_tight = ROOT.TCanvas(str(uuid.uuid4()), '')

        can_proj_lead = ROOT.TCanvas(str(uuid.uuid4()), '')
        can_proj_subl = ROOT.TCanvas(str(uuid.uuid4()), '')

        namePostfix = '__%s-%s' %( lead_reg, subl_reg )
        if lead_ptrange[0] is not None :
            if lead_ptrange[1] is None :
                namePostfix += '__pt_%d-max' %( lead_ptrange[0])
            else :
                namePostfix += '__pt_%d-%d' %( lead_ptrange[0], lead_ptrange[1])

        if subl_ptrange[0] is not None :
            if subl_ptrange[1] is None :
                namePostfix += '__sublpt_%d-max' %( subl_ptrange[0])
            else :
                namePostfix += '__sublpt_%d-%d' %( subl_ptrange[0], subl_ptrange[1])

        outputNamePLST = None
        outputNamePLSL = None
        outputNamePSLT = None
        outputNamePSLL = None
        outputNamePL = None
        outputNamePS = None
        if outputDir is not None :
            outputNamePLST = outputDir + '/fit_with_data_proj_lead_subl_tight%s%s.pdf' %(outputPrefix, namePostfix)
            outputNamePLSL = outputDir + '/fit_with_data_proj_lead_subl_loose%s%s.pdf' %(outputPrefix, namePostfix)
            outputNamePSLT = outputDir + '/fit_with_data_proj_subl_lead_tight%s%s.pdf' %(outputPrefix, namePostfix)
            outputNamePSLL = outputDir + '/fit_with_data_proj_subl_lead_loose%s%s.pdf' %(outputPrefix, namePostfix)
            outputNamePL = outputDir + '/fit_with_data_proj_lead_%s%s.pdf' %(outputPrefix, namePostfix)
            outputNamePS = outputDir + '/fit_with_data_proj_subl_%s%s.pdf' %(outputPrefix, namePostfix)

        if fitvar == 'sigmaIEIE' :
            labvar = '#sigma i#eta i#eta'
        elif fitvar == 'chIsoCorr' :
            labvar = 'chHadIso'
        elif fitvar == 'neuIsoCorr' :
            labvar = 'neuHadIso'
        elif fitvar == 'phoIsoCorr' :
            labvar = 'phoHadIso'

        logy=False

        draw_template(can_proj_lead_subl_loose, [gg_hist_proj_lead_subl_loose, hist_temp_rr_subl_loose, hist_temp_rf_subl_loose, hist_temp_fr_subl_loose, hist_temp_ff_subl_loose], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePLSL, label='#splitline{Lead %s}{sublead loose}' %labvar, axis_label=labvar, logy=logy)
        draw_template(can_proj_lead_subl_tight, [gg_hist_proj_lead_subl_tight, hist_temp_rr_subl_tight, hist_temp_rf_subl_tight, hist_temp_fr_subl_tight, hist_temp_ff_subl_tight], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePLST, label='#splitline{Lead %s}{sublead tight}' %labvar, axis_label=labvar, logy=logy )

        draw_template(can_proj_subl_lead_loose, [gg_hist_proj_subl_lead_loose, hist_temp_rr_lead_loose, hist_temp_rf_lead_loose, hist_temp_fr_lead_loose, hist_temp_ff_lead_loose], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePSLL, label='#splitline{Sublead %s}{lead loose}' %labvar, axis_label=labvar, logy=logy )
        draw_template(can_proj_subl_lead_tight, [gg_hist_proj_subl_lead_tight, hist_temp_rr_lead_tight, hist_temp_rf_lead_tight, hist_temp_fr_lead_tight, hist_temp_ff_lead_tight], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePSLT, label='#splitline{Sublead %s}{lead tight}'  %labvar, axis_label=labvar, logy=logy)

        draw_template(can_proj_lead, [gg_hist_proj_lead, hist_temp_rr_proj_lead, hist_temp_rf_proj_lead, hist_temp_fr_proj_lead, hist_temp_ff_proj_lead], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePL, label='Lead %s' %labvar, axis_label=labvar )
        draw_template(can_proj_subl, [gg_hist_proj_subl, hist_temp_rr_proj_subl, hist_temp_rf_proj_subl, hist_temp_fr_proj_subl, hist_temp_ff_proj_subl], sampManData, normalize=False, first_hist_is_data=True, legend_entries=['Data', 'real+real prediction', 'real+fake prediction', 'fake+real prediction', 'fake+fake prediction' ], outputName=outputNamePL, label='Sublead %s' %labvar, axis_label=labvar )

    text_results_stat_dataSB       = collect_results( results_stat_dataSB      , Ndata, eff_2d_nouncert , templates, eff_cuts, ndim)
    text_results_stat_dataSR       = collect_results( results_stat_dataSR      , Ndata, eff_2d_nouncert , templates, eff_cuts, ndim)
    text_results_stat_temp_tight = collect_results( results_stat_temp_tight, Ndata, eff_results['stat_tight'] , templates, eff_cuts, ndim)
    text_results_stat_temp_loose = collect_results( results_stat_temp_loose, Ndata, eff_results['stat_loose'] , templates, eff_cuts, ndim)
    text_results_stat_ff         = collect_results( results_stat_ff        , Ndata, eff_results['stat_ff'] , templates, eff_cuts, ndim)
    text_results_syst_bkg        = collect_results( results_syst_bkg       , Ndata, eff_results['syst_bkg']   , templates, eff_cuts, ndim)
    text_results_syst_temp       = collect_results( results_syst_temp      , Ndata, eff_results['syst_temp']  , templates, eff_cuts, ndim)

    return text_results_stat_dataSR,text_results_stat_dataSB, text_results_stat_temp_tight, text_results_stat_temp_loose, text_results_stat_ff, text_results_syst_bkg, text_results_syst_temp
    
def format_hist( hist, color ) :

    hist.SetLineColor( color )
    hist.SetMarkerColor( color )

    hist.SetLineWidth(2)
    hist.SetMarkerSize(0)
    hist.SetStats(0)



def run_fit( data, efficiencies ) :

    # make the matrix
    matrix = generate_eff_matrix( efficiencies, ndim=len(data) )

    #do the fit!  Invert the matrix and multiply the by counts vectors
    if len( data ) == 3 :
        results = solve_matrix_eq( matrix, [data['TL'], data['LT'], data['LL']] )
    elif len(data) == 4 :
        #_nmatrix_calls += 1
        results = solve_matrix_eq( matrix, [data['TT'],data['TL'], data['LT'], data['LL']] )


    return results 

def run_fit_manual( data, eff ) :

    # matrix is 
    # ----------------------
    # RF_TL FR_TL FF_TL
    # RF_LT FR_LT FF_LT
    # RF_LL FR_LL FF_LL
    
    # RF_TL = (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']
    # FR_TL = (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']
    # FF_TL = (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']
    # RF_LT = eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])
    # FR_LT = eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])
    # FF_LT = eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])
    # RF_LL = eff['eff_R_L_lead']*eff['eff_F_L_subl']
    # FR_LL = eff['eff_F_L_lead']*eff['eff_R_L_subl']
    # FF_LL = eff['eff_F_L_lead']*eff['eff_F_L_subl']
    # RF_TT = (1-eff['eff_R_L_lead'])*(1-eff['eff_F_L_subl'])
    # FR_TT = (1-eff['eff_F_L_lead'])*(1-eff['eff_R_L_subl'])
    # FF_TT = (1-eff['eff_F_L_lead'])*(1-eff['eff_F_L_subl'])

    # determinant = RF_TL*FR_LT*FF_LL + FR_TL*FF_LT*RF_LL + FF_TL*RF_LT*FR_LL - FF_TL*FR_LT*RF_LL - FR_TL*RF_LT*FF_LL - RF_TL*FF_LT*FR_LL
    # determinant = (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl'] 
    #             + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    #             + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    #             - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    #             - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
    #             - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    
    # Inverted matrix
    # Inv_11 = FR_LT*FF_LL-FF_LT*FR_LL
    # Inv_12 = FF_TL*FR_LL-FR_TL*FF_LL
    # Inv_13 = FR_TL*FF_LT-FF_TL*FR_LT
    # Inv_21 = FF_LT*RF_LL-RF_LT*FF_LL
    # Inv_22 = RF_TL*FF_LL-FF_TL*RF_LL
    # Inv_23 = FF_TL*RF_LT-RF_TL*FF_LT
    # Inv_31 = RF_LT*FR_LL-FR_LT*RF_LL
    # Inv_32 = FR_TL*RF_LL-RF_TL*FR_LL
    # Inv_33 = RF_TL*FR_LT-FR_TL*RF_LT

    # Inv_11 = eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
    #        - eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    # Inv_12 = (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    #        - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl']
    # Inv_13 = (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])
    #        - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])
    # Inv_21 = eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    #        - eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
    # Inv_22 = (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl']
    #        - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    # Inv_23 = (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])
    #        - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])
    # Inv_31 = eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    #        - eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    # Inv_32 = (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl']
    #        - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl']
    # Inv_33 = (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])
    #        - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])

    # alpha_rf = (1/determinant) * ( Inv_11 * Data['TL'] + Inv_12*Data['LT'] + Inv_13 * Data['LL'])
    # alpha_fr = (1/determinant) * ( Inv_21 * Data['TL'] + Inv_22*Data['LT'] + Inv_23 * Data['LL'])
    # alpha_ff = (1/determinant) * ( Inv_31 * Data['TL'] + Inv_32*Data['LT'] + Inv_33 * Data['LL'])
    alpha_rf = ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl'] 
                      + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                      + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                      - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                      - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                      - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
              * ( (  eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                   - eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] )*data['TL']
                + (  (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                   - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl'] )*data['LT']
                + (   (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl']) )*data['LL']
              ) )

    alpha_fr = ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']     
                    + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
            * ( (   eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                  - eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl'] )*data['TL'] 
              + (   (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                  - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl'] )*data['LT']
              + (   (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])
                  - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl']) ) *data['LL']
              ) )
                
    alpha_ff = ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']    
                    + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
            * ( (   eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                  - eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl'] )*data['TL']
              + (  (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                 - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) * data['LT']
              + (   (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])
                  - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl']) )*data['LL']
              ) )


    nPred_RF_TT = ( (1-eff['eff_R_L_lead'])*(1-eff['eff_F_L_subl'])* 
                      ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl'] 
                      + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                      + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                      - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                      - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                      - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
              * ( (  eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                   - eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] )*data['TL']
                + (  (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                   - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl'] )*data['LT']
                + (   (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl']) )*data['LL']
              ) ) )

    nPred_FR_TT = ( (1-eff['eff_F_L_lead'])*(1-eff['eff_R_L_subl'])* 
                   ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']     
                    + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
            * ( (   eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                  - eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl'] )*data['TL'] 
              + (   (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                  - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl'] )*data['LT']
              + (   (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])
                  - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl']) ) *data['LL']
              ) ) )

    nPred_FF_TT = ( (1-eff['eff_F_L_lead'])*(1-eff['eff_F_L_subl'])* 
                  ( (1.0/( (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']    
                    + (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    + (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_F_L_subl']
                    - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) )
            * ( (   eff['eff_R_L_lead']*(1-eff['eff_F_L_subl'])*eff['eff_F_L_lead']*eff['eff_R_L_subl']
                  - eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])*eff['eff_R_L_lead']*eff['eff_F_L_subl'] )*data['TL']
              + (  (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*eff['eff_F_L_subl']
                 - (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*eff['eff_R_L_subl'] ) * data['LT']
              + (   (1-eff['eff_R_L_lead'])*eff['eff_F_L_subl']*eff['eff_F_L_lead']*(1-eff['eff_R_L_subl'])
                  - (1-eff['eff_F_L_lead'])*eff['eff_R_L_subl']*eff['eff_R_L_lead']*(1-eff['eff_F_L_subl']) )*data['LL']
              ) ) )
       
    return {'alpha_RF' : alpha_rf, 'alpha_FR' : alpha_fr, 'alpha_FF' : alpha_ff, 'pred_RF_TT' : nPred_RF_TT, 'pred_FR_TT' : nPred_FR_TT, 'pred_FF_TT' : nPred_FF_TT }
       
       
#def save_normalized_template_hists( data_hist, results, templates, efficiencies, bins_lead_loose, bins_subl_loose, ndim, lead_ptrange=None, subl_ptrange=None, outputDir=None ) :
#    
#    if outputDir is None :
#        return


def collect_results( results, data, efficiencies, templates, cuts, ndim  ) :

    text_results = collections.OrderedDict()

    for key, val in efficiencies.iteritems() :
        text_results[key] = val

    if ndim == 4 :

        text_results['Ndata_TT'] = data['TT']
        text_results['Ndata_TL'] = data['TL']
        text_results['Ndata_LT'] = data['LT']
        text_results['Ndata_LL'] = data['LL']

        text_results['alpha_RR'] = results.item(0)
        text_results['alpha_RF'] = results.item(1)
        text_results['alpha_FR'] = results.item(2)
        text_results['alpha_FF'] = results.item(3)

        text_results['Npred_RR_TT'] = text_results['alpha_RR']*text_results['eff_RR_TT']
        text_results['Npred_RR_TL'] = text_results['alpha_RR']*text_results['eff_RR_TL']
        text_results['Npred_RR_LT'] = text_results['alpha_RR']*text_results['eff_RR_LT']
        text_results['Npred_RR_LL'] = text_results['alpha_RR']*text_results['eff_RR_LL']

    else :
        text_results['Ndata_TT'] = ufloat(0, 0)
        text_results['Ndata_TL'] = data['TL']
        text_results['Ndata_LT'] = data['LT']
        text_results['Ndata_LL'] = data['LL']

        text_results['alpha_RF'] = results.item(0)
        text_results['alpha_FR'] = results.item(1)
        text_results['alpha_FF'] = results.item(2)


    text_results['Npred_RF_TT'] = text_results['alpha_RF']*text_results['eff_RF_TT']
    text_results['Npred_RF_TL'] = text_results['alpha_RF']*text_results['eff_RF_TL']
    text_results['Npred_RF_LT'] = text_results['alpha_RF']*text_results['eff_RF_LT']
    text_results['Npred_RF_LL'] = text_results['alpha_RF']*text_results['eff_RF_LL']

    text_results['Npred_FR_TT'] = text_results['alpha_FR']*text_results['eff_FR_TT']
    text_results['Npred_FR_TL'] = text_results['alpha_FR']*text_results['eff_FR_TL']
    text_results['Npred_FR_LT'] = text_results['alpha_FR']*text_results['eff_FR_LT']
    text_results['Npred_FR_LL'] = text_results['alpha_FR']*text_results['eff_FR_LL']

    text_results['Npred_FF_TT'] = text_results['alpha_FF']*text_results['eff_FF_TT']
    text_results['Npred_FF_TL'] = text_results['alpha_FF']*text_results['eff_FF_TL']
    text_results['Npred_FF_LT'] = text_results['alpha_FF']*text_results['eff_FF_LT']
    text_results['Npred_FF_LL'] = text_results['alpha_FF']*text_results['eff_FF_LL']

    # add the template integrals to results

    bins_lead_tight = ( templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][0] ), templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][1] ) )
    bins_lead_loose = ( templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][0] ), templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][1] ) )
    bins_subl_tight = ( templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][0] ), templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][1] ) )
    bins_subl_loose = ( templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][0] ), templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][1] ) )
     
    int_lead_real_loose = get_integral_and_error(templates['lead']['real']['Data'], bins_lead_loose )
    int_lead_real_tight = get_integral_and_error(templates['lead']['real']['Data'], bins_lead_tight )
    int_lead_fake_loose = get_integral_and_error(templates['lead']['fake']['Data'], bins_lead_loose )
    int_lead_fake_tight = get_integral_and_error(templates['lead']['fake']['Data'], bins_lead_tight )

    int_subl_real_loose = get_integral_and_error(templates['subl']['real']['Data'], bins_subl_loose )
    int_subl_real_tight = get_integral_and_error(templates['subl']['real']['Data'], bins_subl_tight )
    int_subl_fake_loose = get_integral_and_error(templates['subl']['fake']['Data'], bins_subl_loose )
    int_subl_fake_tight = get_integral_and_error(templates['subl']['fake']['Data'], bins_subl_tight )


    if templates['lead']['real']['Background'] is not None :
        int_lead_real_loose = int_lead_real_loose +  get_integral_and_error(templates['lead']['real']['Background'], bins_lead_loose )
    if templates['lead']['real']['Background'] is not None :
        int_lead_real_tight = int_lead_real_tight +  get_integral_and_error(templates['lead']['real']['Background'], bins_lead_tight )
    if templates['lead']['fake']['Background'] is not None :
        int_lead_fake_loose = int_lead_fake_loose +  get_integral_and_error(templates['lead']['fake']['Background'], bins_lead_loose )
    if templates['lead']['fake']['Background'] is not None :
        int_lead_fake_tight = int_lead_fake_tight +  get_integral_and_error(templates['lead']['fake']['Background'], bins_lead_tight )

    if templates['subl']['real']['Background'] is not None :
        int_subl_real_loose = int_subl_real_loose +  get_integral_and_error(templates['subl']['real']['Background'], bins_subl_loose )
    if templates['subl']['real']['Background'] is not None :
        int_subl_real_tight = int_subl_real_tight +  get_integral_and_error(templates['subl']['real']['Background'], bins_subl_tight )
    if templates['subl']['fake']['Background'] is not None :
        int_subl_fake_loose = int_subl_fake_loose +  get_integral_and_error(templates['subl']['fake']['Background'], bins_subl_loose )
    if templates['subl']['fake']['Background'] is not None :
        int_subl_fake_tight = int_subl_fake_tight +  get_integral_and_error(templates['subl']['fake']['Background'], bins_subl_tight )

    text_results['template_int_lead_real_loose'] = int_lead_real_loose
    text_results['template_int_lead_real_tight'] = int_lead_real_tight
    text_results['template_int_lead_fake_loose'] = int_lead_fake_loose
    text_results['template_int_lead_fake_tight'] = int_lead_fake_tight
    text_results['template_int_subl_real_loose'] = int_subl_real_loose
    text_results['template_int_subl_real_tight'] = int_subl_real_tight
    text_results['template_int_subl_fake_loose'] = int_subl_fake_loose
    text_results['template_int_subl_fake_tight'] = int_subl_fake_tight

    return text_results


def generate_1d_efficiencies( templates, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=None, systematics=None ) :

    (int_stat, int_syst) = get_template_integrals( templates, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=var, systematics=systematics )

    (eff_1d_stat_tight, eff_1d_stat_loose, eff_1d_syst_bkg, eff_1d_syst_temp) = get_1d_loose_efficiencies( int_stat, int_syst, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=var, systematics=systematics )



    return eff_1d_stat_tight, eff_1d_stat_loose, eff_1d_syst_bkg, eff_1d_syst_temp

def generate_2d_efficiencies( templates, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=None, systematics=None ) :

    (int_stat, int_syst) = get_template_integrals( templates, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=var, systematics=systematics )

    # get efficiencies with three sources of uncertainty
    # 1) statistical uncertainty on templates
    # 2) systematic uncertainty on background subtraction
    # 3) systematic uncertainty on template shapes
    # 
    # The integrals from get_template_integrals
    # give 1) and 2)

    eff_results = {}


    (eff_1d_stat_tight, eff_1d_stat_loose, eff_1d_syst_bkg, eff_1d_syst_temp) = get_1d_loose_efficiencies( int_stat, int_syst, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=var, systematics=systematics )


    eff_stat_tight = collections.OrderedDict()
    eff_stat_loose = collections.OrderedDict()
    eff_syst_bkg   = collections.OrderedDict()
    eff_syst_temp  = collections.OrderedDict()

    stat_tight_eff_R_L_lead = eff_1d_stat_tight['eff_R_L_lead']
    stat_tight_eff_F_L_lead = eff_1d_stat_tight['eff_F_L_lead']
    stat_tight_eff_R_L_subl = eff_1d_stat_tight['eff_R_L_subl']
    stat_tight_eff_F_L_subl = eff_1d_stat_tight['eff_F_L_subl']

    stat_loose_eff_R_L_lead = eff_1d_stat_loose['eff_R_L_lead']
    stat_loose_eff_F_L_lead = eff_1d_stat_loose['eff_F_L_lead']
    stat_loose_eff_R_L_subl = eff_1d_stat_loose['eff_R_L_subl']
    stat_loose_eff_F_L_subl = eff_1d_stat_loose['eff_F_L_subl']

    syst_bkg_eff_R_L_lead = eff_1d_syst_bkg['eff_R_L_lead']
    syst_bkg_eff_F_L_lead = eff_1d_syst_bkg['eff_F_L_lead']
    syst_bkg_eff_R_L_subl = eff_1d_syst_bkg['eff_R_L_subl']
    syst_bkg_eff_F_L_subl = eff_1d_syst_bkg['eff_F_L_subl']

    syst_temp_eff_R_L_lead = eff_1d_syst_temp['eff_R_L_lead']
    syst_temp_eff_F_L_lead = eff_1d_syst_temp['eff_F_L_lead']
    syst_temp_eff_R_L_subl = eff_1d_syst_temp['eff_R_L_subl']
    syst_temp_eff_F_L_subl = eff_1d_syst_temp['eff_F_L_subl']

    # tight efficiencies are just 1-loose efficiencies
    stat_tight_eff_R_T_lead = ufloat(1.0, 0.0) - stat_tight_eff_R_L_lead
    stat_tight_eff_F_T_lead = ufloat(1.0, 0.0) - stat_tight_eff_F_L_lead
    stat_tight_eff_R_T_subl = ufloat(1.0, 0.0) - stat_tight_eff_R_L_subl
    stat_tight_eff_F_T_subl = ufloat(1.0, 0.0) - stat_tight_eff_F_L_subl

    stat_loose_eff_R_T_lead = ufloat(1.0, 0.0) - stat_loose_eff_R_L_lead
    stat_loose_eff_F_T_lead = ufloat(1.0, 0.0) - stat_loose_eff_F_L_lead
    stat_loose_eff_R_T_subl = ufloat(1.0, 0.0) - stat_loose_eff_R_L_subl
    stat_loose_eff_F_T_subl = ufloat(1.0, 0.0) - stat_loose_eff_F_L_subl

    syst_bkg_eff_R_T_lead = ufloat(1.0, 0.0)  - syst_bkg_eff_R_L_lead
    syst_bkg_eff_F_T_lead = ufloat(1.0, 0.0)  - syst_bkg_eff_F_L_lead
    syst_bkg_eff_R_T_subl = ufloat(1.0, 0.0)  - syst_bkg_eff_R_L_subl
    syst_bkg_eff_F_T_subl = ufloat(1.0, 0.0)  - syst_bkg_eff_F_L_subl

    syst_temp_eff_R_T_lead = ufloat(1.0, 0.0)  - syst_temp_eff_R_L_lead
    syst_temp_eff_F_T_lead = ufloat(1.0, 0.0)  - syst_temp_eff_F_L_lead
    syst_temp_eff_R_T_subl = ufloat(1.0, 0.0)  - syst_temp_eff_R_L_subl
    syst_temp_eff_F_T_subl = ufloat(1.0, 0.0)  - syst_temp_eff_F_L_subl

    print 'syst_bkg_eff_R_L_lead ',syst_bkg_eff_R_L_lead  
    print 'syst_bkg_eff_F_L_lead ',syst_bkg_eff_F_L_lead  
    print 'syst_bkg_eff_R_L_subl ',syst_bkg_eff_R_L_subl  
    print 'syst_bkg_eff_F_L_subl ',syst_bkg_eff_F_L_subl  

    print 'syst_bkg_eff_R_T_lead ',syst_bkg_eff_R_T_lead
    print 'syst_bkg_eff_F_T_lead ',syst_bkg_eff_F_T_lead
    print 'syst_bkg_eff_R_T_subl ',syst_bkg_eff_R_T_subl
    print 'syst_bkg_eff_F_T_subl ',syst_bkg_eff_F_T_subl

    print 'syst_temp_eff_R_L_lead ',syst_temp_eff_R_L_lead  
    print 'syst_temp_eff_F_L_lead ',syst_temp_eff_F_L_lead  
    print 'syst_temp_eff_R_L_subl ',syst_temp_eff_R_L_subl  
    print 'syst_temp_eff_F_L_subl ',syst_temp_eff_F_L_subl  

    print 'syst_temp_eff_R_T_lead ',syst_temp_eff_R_T_lead
    print 'syst_temp_eff_F_T_lead ',syst_temp_eff_F_T_lead
    print 'syst_temp_eff_R_T_subl ',syst_temp_eff_R_T_subl
    print 'syst_temp_eff_F_T_subl ',syst_temp_eff_F_T_subl

    # store the 1-d efficiencies in the
    eff_stat_tight['eff_1d'] = eff_1d_stat_tight
    eff_stat_loose['eff_1d'] = eff_1d_stat_loose
    eff_syst_bkg  ['eff_1d'] = eff_1d_syst_bkg
    eff_syst_temp ['eff_1d'] = eff_1d_syst_temp

    eff_stat_tight['eff_RR_TT'] = stat_tight_eff_R_T_lead*stat_tight_eff_R_T_subl 
    eff_stat_tight['eff_RR_TL'] = stat_tight_eff_R_T_lead*stat_tight_eff_R_L_subl 
    eff_stat_tight['eff_RR_LT'] = stat_tight_eff_R_L_lead*stat_tight_eff_R_T_subl 
    eff_stat_tight['eff_RR_LL'] = stat_tight_eff_R_L_lead*stat_tight_eff_R_L_subl 

    eff_stat_tight['eff_RF_TT'] = stat_tight_eff_R_T_lead*stat_tight_eff_F_T_subl 
    eff_stat_tight['eff_RF_TL'] = stat_tight_eff_R_T_lead*stat_tight_eff_F_L_subl 
    eff_stat_tight['eff_RF_LT'] = stat_tight_eff_R_L_lead*stat_tight_eff_F_T_subl 
    eff_stat_tight['eff_RF_LL'] = stat_tight_eff_R_L_lead*stat_tight_eff_F_L_subl 

    eff_stat_tight['eff_FR_TT'] = stat_tight_eff_F_T_lead*stat_tight_eff_R_T_subl 
    eff_stat_tight['eff_FR_TL'] = stat_tight_eff_F_T_lead*stat_tight_eff_R_L_subl 
    eff_stat_tight['eff_FR_LT'] = stat_tight_eff_F_L_lead*stat_tight_eff_R_T_subl 
    eff_stat_tight['eff_FR_LL'] = stat_tight_eff_F_L_lead*stat_tight_eff_R_L_subl 

    eff_stat_tight['eff_FF_TT'] = stat_tight_eff_F_T_lead*stat_tight_eff_F_T_subl 
    eff_stat_tight['eff_FF_TL'] = stat_tight_eff_F_T_lead*stat_tight_eff_F_L_subl 
    eff_stat_tight['eff_FF_LT'] = stat_tight_eff_F_L_lead*stat_tight_eff_F_T_subl 
    eff_stat_tight['eff_FF_LL'] = stat_tight_eff_F_L_lead*stat_tight_eff_F_L_subl 

    eff_stat_loose['eff_RR_TT'] = stat_loose_eff_R_T_lead*stat_loose_eff_R_T_subl 
    eff_stat_loose['eff_RR_TL'] = stat_loose_eff_R_T_lead*stat_loose_eff_R_L_subl 
    eff_stat_loose['eff_RR_LT'] = stat_loose_eff_R_L_lead*stat_loose_eff_R_T_subl 
    eff_stat_loose['eff_RR_LL'] = stat_loose_eff_R_L_lead*stat_loose_eff_R_L_subl 

    eff_stat_loose['eff_RF_TT'] = stat_loose_eff_R_T_lead*stat_loose_eff_F_T_subl 
    eff_stat_loose['eff_RF_TL'] = stat_loose_eff_R_T_lead*stat_loose_eff_F_L_subl 
    eff_stat_loose['eff_RF_LT'] = stat_loose_eff_R_L_lead*stat_loose_eff_F_T_subl 
    eff_stat_loose['eff_RF_LL'] = stat_loose_eff_R_L_lead*stat_loose_eff_F_L_subl 

    eff_stat_loose['eff_FR_TT'] = stat_loose_eff_F_T_lead*stat_loose_eff_R_T_subl 
    eff_stat_loose['eff_FR_TL'] = stat_loose_eff_F_T_lead*stat_loose_eff_R_L_subl 
    eff_stat_loose['eff_FR_LT'] = stat_loose_eff_F_L_lead*stat_loose_eff_R_T_subl 
    eff_stat_loose['eff_FR_LL'] = stat_loose_eff_F_L_lead*stat_loose_eff_R_L_subl 

    eff_stat_loose['eff_FF_TT'] = stat_loose_eff_F_T_lead*stat_loose_eff_F_T_subl 
    eff_stat_loose['eff_FF_TL'] = stat_loose_eff_F_T_lead*stat_loose_eff_F_L_subl 
    eff_stat_loose['eff_FF_LT'] = stat_loose_eff_F_L_lead*stat_loose_eff_F_T_subl 
    eff_stat_loose['eff_FF_LL'] = stat_loose_eff_F_L_lead*stat_loose_eff_F_L_subl 

    eff_syst_bkg['eff_RR_TT'] = syst_bkg_eff_R_T_lead*syst_bkg_eff_R_T_subl 
    eff_syst_bkg['eff_RR_TL'] = syst_bkg_eff_R_T_lead*syst_bkg_eff_R_L_subl 
    eff_syst_bkg['eff_RR_LT'] = syst_bkg_eff_R_L_lead*syst_bkg_eff_R_T_subl 
    eff_syst_bkg['eff_RR_LL'] = syst_bkg_eff_R_L_lead*syst_bkg_eff_R_L_subl 

    eff_syst_bkg['eff_RF_TT'] = syst_bkg_eff_R_T_lead*syst_bkg_eff_F_T_subl 
    eff_syst_bkg['eff_RF_TL'] = syst_bkg_eff_R_T_lead*syst_bkg_eff_F_L_subl 
    eff_syst_bkg['eff_RF_LT'] = syst_bkg_eff_R_L_lead*syst_bkg_eff_F_T_subl 
    eff_syst_bkg['eff_RF_LL'] = syst_bkg_eff_R_L_lead*syst_bkg_eff_F_L_subl 

    eff_syst_bkg['eff_FR_TT'] = syst_bkg_eff_F_T_lead*syst_bkg_eff_R_T_subl 
    eff_syst_bkg['eff_FR_TL'] = syst_bkg_eff_F_T_lead*syst_bkg_eff_R_L_subl 
    eff_syst_bkg['eff_FR_LT'] = syst_bkg_eff_F_L_lead*syst_bkg_eff_R_T_subl 
    eff_syst_bkg['eff_FR_LL'] = syst_bkg_eff_F_L_lead*syst_bkg_eff_R_L_subl 

    eff_syst_bkg['eff_FF_TT'] = syst_bkg_eff_F_T_lead*syst_bkg_eff_F_T_subl 
    eff_syst_bkg['eff_FF_TL'] = syst_bkg_eff_F_T_lead*syst_bkg_eff_F_L_subl 
    eff_syst_bkg['eff_FF_LT'] = syst_bkg_eff_F_L_lead*syst_bkg_eff_F_T_subl 
    eff_syst_bkg['eff_FF_LL'] = syst_bkg_eff_F_L_lead*syst_bkg_eff_F_L_subl 

    eff_syst_temp['eff_RR_TT'] = syst_temp_eff_R_T_lead*syst_temp_eff_R_T_subl 
    eff_syst_temp['eff_RR_TL'] = syst_temp_eff_R_T_lead*syst_temp_eff_R_L_subl 
    eff_syst_temp['eff_RR_LT'] = syst_temp_eff_R_L_lead*syst_temp_eff_R_T_subl 
    eff_syst_temp['eff_RR_LL'] = syst_temp_eff_R_L_lead*syst_temp_eff_R_L_subl 

    eff_syst_temp['eff_RF_TT'] = syst_temp_eff_R_T_lead*syst_temp_eff_F_T_subl 
    eff_syst_temp['eff_RF_TL'] = syst_temp_eff_R_T_lead*syst_temp_eff_F_L_subl 
    eff_syst_temp['eff_RF_LT'] = syst_temp_eff_R_L_lead*syst_temp_eff_F_T_subl 
    eff_syst_temp['eff_RF_LL'] = syst_temp_eff_R_L_lead*syst_temp_eff_F_L_subl 

    eff_syst_temp['eff_FR_TT'] = syst_temp_eff_F_T_lead*syst_temp_eff_R_T_subl 
    eff_syst_temp['eff_FR_TL'] = syst_temp_eff_F_T_lead*syst_temp_eff_R_L_subl 
    eff_syst_temp['eff_FR_LT'] = syst_temp_eff_F_L_lead*syst_temp_eff_R_T_subl 
    eff_syst_temp['eff_FR_LL'] = syst_temp_eff_F_L_lead*syst_temp_eff_R_L_subl 

    eff_syst_temp['eff_FF_TT'] = syst_temp_eff_F_T_lead*syst_temp_eff_F_T_subl 
    eff_syst_temp['eff_FF_TL'] = syst_temp_eff_F_T_lead*syst_temp_eff_F_L_subl 
    eff_syst_temp['eff_FF_LT'] = syst_temp_eff_F_L_lead*syst_temp_eff_F_T_subl 
    eff_syst_temp['eff_FF_LL'] = syst_temp_eff_F_L_lead*syst_temp_eff_F_L_subl 

    eff_results['stat_tight'] = eff_stat_tight
    eff_results['stat_loose'] = eff_stat_loose
    eff_results['syst_bkg']   = eff_syst_bkg
    eff_results['syst_temp']  = eff_syst_temp

    return eff_results


def generate_2d_corr_efficiencies( template, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=None ) :

    # integrate each region of the 2-d template

    #lead is on y axis, subl on x
    bin_subl_tight = ( template['leadPass'].GetXaxis().FindBin( cuts['subl']['tight'][0] ), template['leadPass'].GetXaxis().FindBin( cuts['subl']['tight'][1] ) )
    bin_subl_loose = ( template['leadPass'].GetXaxis().FindBin( cuts['subl']['loose'][0] ), template['leadPass'].GetXaxis().FindBin( cuts['subl']['loose'][1] ) )

    err_lead_tight_subl_tight = ROOT.Double()
    int_lead_tight_subl_tight = template['leadPass'].IntegralAndError( bin_subl_tight[0], bin_subl_tight[1], err_lead_tight_subl_tight )

    err_lead_tight_subl_loose = ROOT.Double()
    int_lead_tight_subl_loose = template['leadPass'].IntegralAndError( bin_subl_loose[0], bin_subl_loose[1], err_lead_tight_subl_loose )

    err_lead_loose_subl_tight = ROOT.Double()
    int_lead_loose_subl_tight = template['leadFail'].IntegralAndError( bin_subl_tight[0], bin_subl_tight[1], err_lead_loose_subl_tight )

    err_lead_loose_subl_loose = ROOT.Double()
    int_lead_loose_subl_loose = template['leadFail'].IntegralAndError( bin_subl_loose[0], bin_subl_loose[1], err_lead_loose_subl_loose )

    int_tt = ufloat( int_lead_tight_subl_tight, err_lead_tight_subl_tight )
    int_tl = ufloat( int_lead_tight_subl_loose, err_lead_tight_subl_loose )
    int_lt = ufloat( int_lead_loose_subl_tight, err_lead_loose_subl_tight )
    int_ll = ufloat( int_lead_loose_subl_loose, err_lead_loose_subl_loose)

    print '2d FF template N TT = ', int_tt
    print '2d FF template N TL = ', int_tl
    print '2d FF template N LT = ', int_lt
    print '2d FF template N LL = ', int_ll

    denominator = int_tt + int_tl + int_lt + int_ll

    if denominator != 0 :
        frac_tt = int_tt/( denominator )
        frac_tl = int_tl/( denominator )
        frac_lt = int_lt/( denominator )
        frac_ll = int_ll/( denominator )
    else :
        frac_tt = ufloat(0,0)
        frac_tl = ufloat(0,0)
        frac_lt = ufloat(0,0)
        frac_ll = ufloat(0,0)

    eff_stat = {}
    eff_syst = {}

    eff_stat['eff_FF_TT'] = frac_tt
    eff_stat['eff_FF_TL'] = frac_tl
    eff_stat['eff_FF_LT'] = frac_lt
    eff_stat['eff_FF_LL'] = frac_ll

    eff_syst['eff_FF_TT'] = frac_tt
    eff_syst['eff_FF_TL'] = frac_tl
    eff_syst['eff_FF_LT'] = frac_lt
    eff_syst['eff_FF_LL'] = frac_ll

    return eff_stat, eff_syst




def get_1d_loose_efficiencies( int_stat, int_syst, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=None, systematics=None) :

    eff_stat = {}
    eff_stat_tight = {}
    eff_stat_loose = {}
    eff_syst_int = {}
    eff_syst_temp = {}

    eff_stat['eff_R_L_lead'] = int_stat['lead']['real']['loose'] / (int_stat['lead']['real']['tight']+int_stat['lead']['real']['loose'])
    eff_stat['eff_F_L_lead'] = int_stat['lead']['fake']['loose'] / (int_stat['lead']['fake']['tight']+int_stat['lead']['fake']['loose'])
    eff_stat['eff_R_L_subl'] = int_stat['subl']['real']['loose'] / (int_stat['subl']['real']['tight']+int_stat['subl']['real']['loose'])
    eff_stat['eff_F_L_subl'] = int_stat['subl']['fake']['loose'] / (int_stat['subl']['fake']['tight']+int_stat['subl']['fake']['loose'])

    int_stat_notunc = {'lead' : {}, 'subl' : {}}
    int_stat_notunc['lead'] = { 'real' : {}, 'fake' : {} }
    int_stat_notunc['subl'] = { 'real' : {}, 'fake' : {} }

    int_stat_notunc['lead']['real']['tight'] = ufloat( int_stat['lead']['real']['tight'].n, 0.0 )
    int_stat_notunc['lead']['fake']['tight'] = ufloat( int_stat['lead']['fake']['tight'].n, 0.0 )
    int_stat_notunc['subl']['real']['tight'] = ufloat( int_stat['subl']['real']['tight'].n, 0.0 )
    int_stat_notunc['subl']['fake']['tight'] = ufloat( int_stat['subl']['fake']['tight'].n, 0.0 )

    int_stat_nolunc = {'lead' : {}, 'subl' : {}}
    int_stat_nolunc['lead'] = { 'real' : {}, 'fake' : {} }
    int_stat_nolunc['subl'] = { 'real' : {}, 'fake' : {} }

    int_stat_nolunc['lead']['real']['loose'] = ufloat( int_stat['lead']['real']['loose'].n, 0.0 )
    int_stat_nolunc['lead']['fake']['loose'] = ufloat( int_stat['lead']['fake']['loose'].n, 0.0 )
    int_stat_nolunc['subl']['real']['loose'] = ufloat( int_stat['subl']['real']['loose'].n, 0.0 )
    int_stat_nolunc['subl']['fake']['loose'] = ufloat( int_stat['subl']['fake']['loose'].n, 0.0 )


    if int_stat['lead']['real']['loose'].n == 0 :
        eff_stat_loose['eff_R_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_loose['eff_R_L_lead'] = 1.0 / (1.0 + (int_stat_notunc['lead']['real']['tight']/int_stat['lead']['real']['loose']) )
    if int_stat['lead']['fake']['loose'].n == 0 :
        eff_stat_loose['eff_F_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_loose['eff_F_L_lead'] = 1.0 / (1.0 + (int_stat_notunc['lead']['fake']['tight']/int_stat['lead']['fake']['loose']) )
    if int_stat['subl']['real']['loose'].n == 0 :
        eff_stat_loose['eff_R_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_loose['eff_R_L_subl'] = 1.0 / (1.0 + (int_stat_notunc['subl']['real']['tight']/int_stat['subl']['real']['loose']) )
    if int_stat['subl']['fake']['loose'].n == 0 :
        eff_stat_loose['eff_F_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_loose['eff_F_L_subl'] = 1.0 / (1.0 + (int_stat_notunc['subl']['fake']['tight']/int_stat['subl']['fake']['loose']) )

    if int_stat_nolunc['lead']['real']['loose'].n == 0 :
        eff_stat_tight['eff_R_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_tight['eff_R_L_lead'] = 1.0 / (1.0 + (int_stat['lead']['real']['tight']/int_stat_nolunc['lead']['real']['loose']) )
    if int_stat_nolunc['lead']['fake']['loose'].n == 0 :
        eff_stat_tight['eff_F_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_tight['eff_F_L_lead'] = 1.0 / (1.0 + (int_stat['lead']['fake']['tight']/int_stat_nolunc['lead']['fake']['loose']) )
    if int_stat_nolunc['subl']['real']['loose'].n == 0 :
        eff_stat_tight['eff_R_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_tight['eff_R_L_subl'] = 1.0 / (1.0 + (int_stat['subl']['real']['tight']/int_stat_nolunc['subl']['real']['loose']) )
    if int_stat_nolunc['subl']['fake']['loose'].n == 0 :
        eff_stat_tight['eff_F_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_stat_tight['eff_F_L_subl'] = 1.0 / (1.0 + (int_stat['subl']['fake']['tight']/int_stat_nolunc['subl']['fake']['loose']) )


    # make the systematic efficiencies
    # based on the systematics from the
    # input integrals
    if int_syst['lead']['real']['loose'].n == 0 :
        eff_syst_int['eff_R_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_int['eff_R_L_lead'] = 1.0 / ( 1.0 + (int_syst['lead']['real']['tight']/int_syst['lead']['real']['loose']) )
    if int_syst['lead']['fake']['loose'].n == 0 :
        eff_syst_int['eff_F_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_int['eff_F_L_lead'] = 1.0 / ( 1.0 + (int_syst['lead']['fake']['tight']/int_syst['lead']['fake']['loose']) )
    if int_syst['subl']['real']['loose'].n == 0 :
        eff_syst_int['eff_R_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_int['eff_R_L_subl'] = 1.0 / ( 1.0 + (int_syst['subl']['real']['tight']/int_syst['subl']['real']['loose']) )
    if int_syst['subl']['fake']['loose'].n == 0 :
        eff_syst_int['eff_F_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_int['eff_F_L_subl'] = 1.0 / ( 1.0 + (int_syst['subl']['fake']['tight']/int_syst['subl']['fake']['loose']) )

    # make the systematic efficiencies
    # based on the systematics from the
    # templates which are set below
    # first get the ratios
    if int_syst['lead']['real']['loose'].n == 0 :
        eff_syst_temp['eff_R_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_temp['eff_R_L_lead'] = 1.0 / (1.0 + (int_syst['lead']['real']['tight']/int_syst['lead']['real']['loose']) )
    if int_syst['lead']['fake']['loose'].n == 0 :
        eff_syst_temp['eff_F_L_lead'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_temp['eff_F_L_lead'] = 1.0 / (1.0 + (int_syst['lead']['fake']['tight']/int_syst['lead']['fake']['loose']) )
    if int_syst['subl']['real']['loose'].n == 0 :
        eff_syst_temp['eff_R_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_temp['eff_R_L_subl'] = 1.0 / (1.0 + (int_syst['subl']['real']['tight']/int_syst['subl']['real']['loose']) )
    if int_syst['subl']['fake']['loose'].n == 0 :
        eff_syst_temp['eff_F_L_subl'] = ufloat( 0.0, 0.0 ) 
    else :
        eff_syst_temp['eff_F_L_subl'] = 1.0 / (1.0 + (int_syst['subl']['fake']['tight']/int_syst['subl']['fake']['loose']) )

    # get the template uncertainties
    # simply overwrite the current
    # uncertainties so that we have
    # only the template uncertainties
    eff_syst_temp['eff_R_L_lead'] = ufloat( eff_syst_temp['eff_R_L_lead'].n , math.fabs(eff_syst_temp['eff_R_L_lead'].n)*get_syst_uncertainty( var, 'RealTemplate%s'%systematics, lead_reg, lead_ptrange, 'real', 'loose' ), 'Template_lead_real_loose')
    eff_syst_temp['eff_F_L_lead'] = ufloat( eff_syst_temp['eff_F_L_lead'].n , math.fabs(eff_syst_temp['eff_F_L_lead'].n)*get_syst_uncertainty( var, 'FakeTemplate%s'%systematics, lead_reg, lead_ptrange, 'fake', 'loose' ), 'Template_lead_fake_loose' )
    eff_syst_temp['eff_R_L_subl'] = ufloat( eff_syst_temp['eff_R_L_subl'].n , math.fabs(eff_syst_temp['eff_R_L_subl'].n)*get_syst_uncertainty( var, 'RealTemplate%s'%systematics, subl_reg, subl_ptrange, 'real', 'loose' ), 'Template_subl_real_loose' )
    eff_syst_temp['eff_F_L_subl'] = ufloat( eff_syst_temp['eff_F_L_subl'].n , math.fabs(eff_syst_temp['eff_F_L_subl'].n)*get_syst_uncertainty( var, 'FakeTemplate%s'%systematics, subl_reg, subl_ptrange, 'fake', 'loose' ), 'Template_subl_fake_loose' )

    return eff_stat_tight, eff_stat_loose, eff_syst_int, eff_syst_temp

def get_template_integrals( templates, cuts, lead_reg, subl_reg, lead_ptrange, subl_ptrange, var=None, systematics=None) :

    int_stat = {}
    int_stat['lead']={}
    int_stat['subl']={}
    int_stat['lead']['real']={}
    int_stat['subl']['real']={}
    int_stat['lead']['fake']={}
    int_stat['subl']['fake']={}

    int_syst = {}
    int_syst['lead']={}
    int_syst['subl']={}
    int_syst['lead']['real']={}
    int_syst['subl']['real']={}
    int_syst['lead']['fake']={}
    int_syst['subl']['fake']={}

    bins_lead_real_tight = ( templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][0] ), templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][1] ) )
    bins_lead_real_loose = ( templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][0] ), templates['lead']['real']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][1] ) )
    bins_lead_fake_tight = ( templates['lead']['fake']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][0] ), templates['lead']['fake']['Data'].GetXaxis().FindBin( cuts['lead']['tight'][1] ) )
    bins_lead_fake_loose = ( templates['lead']['fake']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][0] ), templates['lead']['fake']['Data'].GetXaxis().FindBin( cuts['lead']['loose'][1] ) )
    bins_subl_real_tight = ( templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][0] ), templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][1] ) )
    bins_subl_real_loose = ( templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][0] ), templates['subl']['real']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][1] ) )
    bins_subl_fake_tight = ( templates['subl']['fake']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][0] ), templates['subl']['fake']['Data'].GetXaxis().FindBin( cuts['subl']['tight'][1] ) )
    bins_subl_fake_loose = ( templates['subl']['fake']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][0] ), templates['subl']['fake']['Data'].GetXaxis().FindBin( cuts['subl']['loose'][1] ) )

    int_stat['lead']['real']['tight'] = get_integral_and_error( templates['lead']['real']['Data'], bins_lead_real_tight, 'Data_lead_real_tight' )
    int_stat['lead']['real']['loose'] = get_integral_and_error( templates['lead']['real']['Data'], bins_lead_real_loose, 'Data_lead_real_loose' )
    int_stat['lead']['fake']['tight'] = get_integral_and_error( templates['lead']['fake']['Data'], bins_lead_fake_tight, 'Data_lead_fake_tight' )
    int_stat['lead']['fake']['loose'] = get_integral_and_error( templates['lead']['fake']['Data'], bins_lead_fake_loose, 'Data_lead_fake_loose' )
    int_stat['subl']['real']['tight'] = get_integral_and_error( templates['subl']['real']['Data'], bins_subl_real_tight, 'Data_subl_real_tight' )
    int_stat['subl']['real']['loose'] = get_integral_and_error( templates['subl']['real']['Data'], bins_subl_real_loose, 'Data_subl_real_loose' )
    int_stat['subl']['fake']['tight'] = get_integral_and_error( templates['subl']['fake']['Data'], bins_subl_fake_tight, 'Data_subl_fake_tight' )
    int_stat['subl']['fake']['loose'] = get_integral_and_error( templates['subl']['fake']['Data'], bins_subl_fake_loose, 'Data_subl_fake_loose' )

    # If running with systematics, set the data systs to zero
    # May need to implement non-zero systematics for data in the future
    # The overall template systematics should not be set here
    int_syst['lead']['real']['tight'] = ufloat(int_stat['lead']['real']['tight'].n, 0.0 , 'Data_lead_real_tight' )
    int_syst['lead']['real']['loose'] = ufloat(int_stat['lead']['real']['loose'].n, 0.0 , 'Data_lead_real_loose' )
    int_syst['lead']['fake']['tight'] = ufloat(int_stat['lead']['fake']['tight'].n, 0.0 , 'Data_lead_fake_tight' )
    int_syst['lead']['fake']['loose'] = ufloat(int_stat['lead']['fake']['loose'].n, 0.0 , 'Data_lead_fake_loose' )
    int_syst['subl']['real']['tight'] = ufloat(int_stat['subl']['real']['tight'].n, 0.0 , 'Data_subl_real_tight' )
    int_syst['subl']['real']['loose'] = ufloat(int_stat['subl']['real']['loose'].n, 0.0 , 'Data_subl_real_loose' )
    int_syst['subl']['fake']['tight'] = ufloat(int_stat['subl']['fake']['tight'].n, 0.0 , 'Data_subl_fake_tight' )
    int_syst['subl']['fake']['loose'] = ufloat(int_stat['subl']['fake']['loose'].n, 0.0 , 'Data_subl_fake_loose' )

    # Subtract background

    if templates['lead']['real']['Background'] is not None :
        bkg_int_tight = get_integral_and_error( templates['lead']['real']['Background'], bins_lead_real_tight, 'Background_lead_real_tight' )
        bkg_int_loose = get_integral_and_error( templates['lead']['real']['Background'], bins_lead_real_loose, 'Background_lead_real_loose'  ) 

        syst_bkg_int_tight = ufloat( bkg_int_tight.n, math.fabs(bkg_int_tight.n)*get_syst_uncertainty( var, 'Background%s'%systematics , lead_reg, lead_ptrange, 'real', 'tight' ), 'Background_lead_real_tight' )
        syst_bkg_int_loose = ufloat( bkg_int_loose.n, math.fabs(bkg_int_loose.n)*get_syst_uncertainty( var, 'Background%s'%systematics, lead_reg , lead_ptrange, 'real', 'loose'), 'Background_lead_real_loose' )

        int_stat['lead']['real']['tight'] = int_stat['lead']['real']['tight'] + bkg_int_tight
        int_stat['lead']['real']['loose'] = int_stat['lead']['real']['loose'] + bkg_int_loose

        int_syst['lead']['real']['tight'] = int_syst['lead']['real']['tight'] + syst_bkg_int_tight
        int_syst['lead']['real']['loose'] = int_syst['lead']['real']['loose'] + syst_bkg_int_loose

    if templates['lead']['fake']['Background'] is not None :
        bkg_int_tight = get_integral_and_error( templates['lead']['fake']['Background'], bins_lead_fake_tight, 'Background_lead_fake_tight'  ) 
        bkg_int_loose = get_integral_and_error( templates['lead']['fake']['Background'], bins_lead_fake_loose, 'Background_lead_fake_loose'  ) 

        syst_bkg_int_tight = ufloat( bkg_int_tight.n, math.fabs(bkg_int_tight.n)*get_syst_uncertainty( var, 'Background%s'%systematics, lead_reg , lead_ptrange, 'fake', 'tight'), 'Background_lead_fake_tight' )
        syst_bkg_int_loose = ufloat( bkg_int_loose.n, math.fabs(bkg_int_loose.n)*get_syst_uncertainty( var, 'Background%s'%systematics, lead_reg , lead_ptrange, 'fake', 'loose'), 'Background_lead_fake_loose' )

        int_stat['lead']['fake']['tight'] = int_stat['lead']['fake']['tight'] + bkg_int_tight
        int_stat['lead']['fake']['loose'] = int_stat['lead']['fake']['loose'] + bkg_int_loose

        int_syst['lead']['fake']['tight'] = int_syst['lead']['fake']['tight'] + syst_bkg_int_tight
        int_syst['lead']['fake']['loose'] = int_syst['lead']['fake']['loose'] + syst_bkg_int_loose

    if templates['subl']['real']['Background'] is not None :

        bkg_int_tight = get_integral_and_error( templates['subl']['real']['Background'], bins_subl_real_tight, 'Background_subl_real_tight'  ) 
        bkg_int_loose = get_integral_and_error( templates['subl']['real']['Background'], bins_subl_real_loose, 'Background_subl_real_loose'  ) 

        syst_bkg_int_tight = ufloat( bkg_int_tight.n, math.fabs(bkg_int_tight.n)*get_syst_uncertainty( var, 'Background%s'%systematics, subl_reg , subl_ptrange, 'real', 'tight'), 'Background_subl_real_tight' )
        syst_bkg_int_loose = ufloat( bkg_int_loose.n, math.fabs(bkg_int_loose.n)*get_syst_uncertainty( var, 'Background%s'%systematics, subl_reg , subl_ptrange, 'real', 'loose'), 'Background_subl_real_loose' )

        int_stat['subl']['real']['tight'] = int_stat['subl']['real']['tight'] + bkg_int_tight
        int_stat['subl']['real']['loose'] = int_stat['subl']['real']['loose'] + bkg_int_loose

        int_syst['subl']['real']['tight'] = int_syst['subl']['real']['tight'] + syst_bkg_int_tight
        int_syst['subl']['real']['loose'] = int_syst['subl']['real']['loose'] + syst_bkg_int_loose

    if templates['subl']['fake']['Background'] is not None :
        bkg_int_tight = get_integral_and_error( templates['subl']['fake']['Background'], bins_subl_fake_tight, 'Background_subl_fake_tight'  ) 
        bkg_int_loose = get_integral_and_error( templates['subl']['fake']['Background'], bins_subl_fake_loose, 'Background_subl_fake_loose'  ) 

        syst_bkg_int_tight = ufloat( bkg_int_tight.n, math.fabs(bkg_int_tight.n)*get_syst_uncertainty( var, 'Background%s'%systematics, subl_reg , subl_ptrange, 'fake', 'tight'), 'Background_subl_fake_tight' )
        syst_bkg_int_loose = ufloat( bkg_int_loose.n, math.fabs(bkg_int_loose.n)*get_syst_uncertainty( var, 'Background%s'%systematics, subl_reg , subl_ptrange, 'fake', 'loose'), 'Background_subl_fake_loose' )
        int_stat['subl']['fake']['tight'] = int_stat['subl']['fake']['tight'] + bkg_int_tight
        int_stat['subl']['fake']['loose'] = int_stat['subl']['fake']['loose'] + bkg_int_loose
        
        int_syst['subl']['fake']['tight'] = int_syst['subl']['fake']['tight'] + syst_bkg_int_tight
        int_syst['subl']['fake']['loose'] = int_syst['subl']['fake']['loose'] + syst_bkg_int_loose

    fix_negative_entries( int_stat )
    fix_negative_entries( int_syst )

    return int_stat, int_syst

def fix_negative_entries( integrals ) :

    for ls in integrals.keys() :
        for rf in integrals[ls].keys() :
            for tl in integrals[ls][rf].keys() :
                val = integrals[ls][rf][tl].n
                if val < 0 :
                    integrals[ls][rf][tl] = ufloat( 0.0, integrals[ls][rf][tl].s )

def get_integral_and_error( hist, bins=None, name='' ) :

    err = ROOT.Double()
    if bins is None :
        val = hist.IntegralAndError( 1, hist.GetNbinsX(), err )
    else :
        if bins[1] is None :
            val = hist.IntegralAndError( bins[0], hist.GetNbinsX(), err )
        else :
            val = hist.IntegralAndError( bins[0], bins[1], err )

    return ufloat( val, err, name )


def get_single_photon_template( selection, binning, sample, reg, fitvar='sigmaIEIE', sampMan=None) :

    if sampMan is None :
        sampMan = sampManLG

    if reg not in ['EB', 'EE'] :
        print 'Region not specified correctly'
        return None

    var = 'ph_pt[0]:ph_%s[0]' %fitvar#y:x

    selection = selection + ' && ph_Is%s[0] ' %( reg )

    data_samp_name = sample['Data']
    bkg_samp_name  = sample.get('Background', None)

    template_hists = {}


    data_samp = sampMan.get_samples(name=data_samp_name )

    if data_samp :
        print '---------------------------------'
        print ' Draw Template for var %s        ' %fitvar
        print 'Binning = ', binning
        print selection
        print '---------------------------------'
    
        template_hists['Data'] = clone_sample_and_draw( data_samp[0], var, selection, ( binning[0], binning[1], binning[2],100, 0, 500  ), useSampMan=sampMan ) 
    else :
        print 'Data template sample not found!'
        
    if bkg_samp_name is not None :
        bkg_samp = sampMan.get_samples(name=bkg_samp_name )

        if bkg_samp :
            print '---------------------------------'
            print ' Draw Template Background for var %s ' %fitvar
            print selection
            print '---------------------------------'
            template_hists['Background'] = clone_sample_and_draw( bkg_samp[0], var, selection, ( binning[0], binning[1], binning[2],100, 0, 500  ), useSampMan=sampMan ) 
        else :
            print 'Background template sample not found!'
    else :
        template_hists['Background']=None

    return template_hists

def get_correlated_fake_fake_templates( selection, binning, sample, reg1, reg2, fitvar='sigmaIEIE', sampMan=None) :

    if sampMan is None :
        sampMan = sampManLG

    if reg1 not in ['EB', 'EE'] or reg2 not in ['EB', 'EE'] :
        print 'Region not specified correctly'
        return None

    fitvarmod = ''
    if fitvar == 'sigmaIEIE' :
        fitvarmod = 'sieie'
    else :
        fitvarmod = fitvar

    var = 'pt_leadph12:%s_sublph12' %(fitvarmod)#y:x

    selection = selection + ' && is%s_leadph12 && is%s_sublph12 ' %( reg1, reg2 )

    data_samp_name = sample['Data']
    bkg_samp_name  = sample.get('Background', None)

    template_hists = {}

    data_samp = sampMan.get_samples(name=data_samp_name )

    if data_samp :
        print '---------------------------------'
        print ' Draw 2-D correlated Template for var %s        ' %fitvar
        print 'Binning = ', ( binning[reg2][0], binning[reg2][1], binning[reg2][2], 100, 0, 500  )
        print selection
        print '---------------------------------'
    
        template_hists['Data'] = clone_sample_and_draw( data_samp[0], var, selection, ( binning[reg2][0], binning[reg2][1], binning[reg2][2], 100, 0, 500  ), useSampMan=sampMan ) 
    else :
        print 'Data template sample not found!'
        
    template_hists['Background']=None

    return template_hists

def generate_eff_matrix( eff_dic, ndim=3 ) :

    eff_matrix = [ [ eff_dic['eff_RF_TL'], eff_dic['eff_FR_TL'], eff_dic['eff_FF_TL'] ],
                   [ eff_dic['eff_RF_LT'], eff_dic['eff_FR_LT'], eff_dic['eff_FF_LT'] ], 
                   [ eff_dic['eff_RF_LL'], eff_dic['eff_FR_LL'], eff_dic['eff_FF_LL'] ] ] 
    
    if ndim == 4 :
        eff_matrix = [ [ eff_dic['eff_RR_TT'], eff_dic['eff_RF_TT'], eff_dic['eff_FR_TT'], eff_dic['eff_FF_TT'] ], 
                       [ eff_dic['eff_RR_TL'], eff_matrix[0][0]    , eff_matrix[0][1]    , eff_matrix[0][2]     ],
                       [ eff_dic['eff_RR_LT'], eff_matrix[1][0]    , eff_matrix[1][1]    , eff_matrix[1][2]     ],
                       [ eff_dic['eff_RR_LL'], eff_matrix[2][0]    , eff_matrix[2][1]    , eff_matrix[2][2]     ] ]

    elif ndim != 3 :
        print 'Only Dim 3 and 4 implemented'
        return None

    return eff_matrix


def solve_matrix_eq( matrix_ntries, vector_entries ) :

    ms = []
    mn = []
    for row in matrix_ntries :
        ms_row = []
        mn_row = []
        for col in row :
            ms_row.append( col.s )
            mn_row.append( col.n )
        ms.append( ms_row )
        mn.append( mn_row )

    matrix = unumpy.umatrix( mn, ms )

    vs = []
    vn = []
    for row in vector_entries :
        vn.append( [ row.n ] )
        vs.append( [ row.s ] )

    vector = unumpy.umatrix( vn, vs )
    
    inv_matrix = None
    try :
        inv_matrix = matrix.getI()
    except :
        print 'Failed to invert matrix, aborting'
        return unumpy.umatrix( [ [1]*len(vs) ], [ [0]*len(vs) ] )

    return inv_matrix*vector

def clone_sample_and_draw( samp, var, sel, binning, useSampMan=None ) :


    if useSampMan is not None :
        newSamp = useSampMan.clone_sample( oldname=samp.name, newname=samp.name+str(uuid.uuid4()), temporary=True ) 
        useSampMan.create_hist( newSamp, var, sel, binning )
        return newSamp.hist

    else :
        newSamp = sampMan.clone_sample( oldname=samp.name, newname=samp.name+str(uuid.uuid4()), temporary=True ) 
        sampMan.create_hist( newSamp, var, sel, binning )
        return newSamp.hist

def config_and_queue_hist( samp, var, sel, binning, useSampMan=None ) :

    if useSampMan is not None :
        useSampMan.activate_sample( samp )
        draw_conf = DrawConfig( var, sel, binning, samples=samp )
        useSampMan.queue_draw( draw_conf )
        return draw_conf
    else :
        sampMan.activate_sample( samp )
        draw_conf = DrawConfig( var, sel, binning, samples=samp )
        sampMan.queue_draw( draw_conf)
        return draw_conf

def save_templates( templates, outputDir, lead_ptrange=(None,None), subl_ptrange=(None,None),namePostfix='' ) :

    if outputDir is None :
        return

    draw_templates = {'lead' : {}, 'subl' : {} }

    draw_templates['lead']['real'] = templates['lead']['real']['Data'].Clone( 'draw_%s' %templates['lead']['real']['Data'].GetName())
    draw_templates['lead']['fake'] = templates['lead']['fake']['Data'].Clone( 'draw_%s' %templates['lead']['fake']['Data'].GetName())
    draw_templates['subl']['real'] = templates['subl']['real']['Data'].Clone( 'draw_%s' %templates['subl']['real']['Data'].GetName())
    draw_templates['subl']['fake'] = templates['subl']['fake']['Data'].Clone( 'draw_%s' %templates['subl']['fake']['Data'].GetName())

    if templates['lead']['real']['Background'] is not None :
        draw_templates['lead']['real'].Add( templates['lead']['real']['Background'])
    if templates['lead']['fake']['Background'] is not None :
        draw_templates['lead']['fake'].Add( templates['lead']['fake']['Background'])
    if templates['subl']['real']['Background'] is not None :
        draw_templates['subl']['real'].Add( templates['subl']['real']['Background'])
    if templates['subl']['fake']['Background'] is not None :
        draw_templates['subl']['fake'].Add( templates['subl']['fake']['Background'])

    can_lead_real = ROOT.TCanvas('can_lead_real', '')
    can_lead_fake = ROOT.TCanvas('can_lead_fake', '')
    can_subl_real = ROOT.TCanvas('can_subl_real', '')
    can_subl_fake = ROOT.TCanvas('can_subl_fake', '')

    pt_label_lead = None
    pt_label_subl = None
    if lead_ptrange[0] is not None :
        if lead_ptrange[1] == None :
            pt_label_lead = ' p_{T} > %d ' %( lead_ptrange[0] )
        else :
            pt_label_lead = ' %d < p_{T} < %d ' %( lead_ptrange[0], lead_ptrange[1] )
    else :
        pt_label_lead = 'p_{T} inclusive'

    if subl_ptrange[0] is not None :
        if subl_ptrange[1] == None :
            pt_label_subl = ' p_{T} > %d ' %( subl_ptrange[0] )
        else :
            pt_label_subl = ' %d < p_{T} < %d ' %( subl_ptrange[0], subl_ptrange[1] )
    else :
        pt_label_subl = 'p_{T} inclusive'

    draw_template( can_lead_real, draw_templates['lead']['real'], sampManData, normalize=1, label=pt_label_lead, outputName = outputDir+'/template_lead_real%s.pdf' %namePostfix )
    draw_template( can_lead_fake, draw_templates['lead']['fake'], sampManData, normalize=1, label=pt_label_lead, outputName = outputDir+'/template_lead_fake%s.pdf' %namePostfix )
    draw_template( can_subl_real, draw_templates['subl']['real'], sampManData, normalize=1, label=pt_label_subl, outputName = outputDir+'/template_subl_real%s.pdf' %namePostfix )
    draw_template( can_subl_fake, draw_templates['subl']['fake'], sampManData, normalize=1, label=pt_label_subl, outputName = outputDir+'/template_subl_fake%s.pdf' %namePostfix )


def save_results( results, outputDir, namePostfix='' ) :

    if outputDir is None :
        return

    fname = outputDir + '/results%s.pickle' %namePostfix

    if not os.path.isdir( os.path.dirname( fname ) ) :
        os.makedirs( os.path.dirname( fname ) )
    file = open( fname, 'w' )
    pickle.dump( results, file, pickle.HIGHEST_PROTOCOL )
    file.close()


def draw_template(can, hists, sampMan, normalize=False, first_hist_is_data=False, axis_label='#sigma i#etai#eta', label=None, legend_entries=[], outputName=None, logy=False ) :

    if not isinstance(hists, list) :
        hists = [hists]

    can.cd()
    can.SetBottomMargin( 0.12 )
    can.SetLeftMargin( 0.12 )

    added_sum_hist=False
    if len(hists) > 1 and not first_hist_is_data or len(hists)>2 and first_hist_is_data :
        if first_hist_is_data :
            hists_to_sum = hists[1:]
        else :
            hists_to_sum = hists

        sumhist = hists_to_sum[0].Clone( 'sumhist%s' %hists_to_sum[0].GetName())
        for h in hists_to_sum[1:] :
            sumhist.Add(h)

        format_hist( sumhist, ROOT.kBlue+1 )
        hists.append(sumhist)
        added_sum_hist=True

    #get y size
    maxbin = hists[0].GetBinContent(hists[0].GetMaximumBin())
    for h in hists[1: ] :
        if h.GetBinContent(h.GetMaximumBin() ) > maxbin :
            maxbin = h.GetBinContent(h.GetMaximumBin() )

    maxval_hist = maxbin * 1.25
    if normalize :
        maxval_axis = maxval_hist/hists[0].Integral()
    else :
        maxval_axis = maxval_hist
        
    for h in hists :        
        h.GetYaxis().SetRangeUser( 0, maxval_hist )
        h.GetXaxis().SetTitleSize( 0.05 )
        h.GetXaxis().SetLabelSize( 0.05 )
        h.GetYaxis().SetTitleSize( 0.05 )
        h.GetYaxis().SetLabelSize( 0.05 )
        h.GetYaxis().SetTitleOffset( 1.15 )
        h.GetXaxis().SetTitle( axis_label )
        h.SetStats(0)
        h.SetLineWidth( 2 )
        bin_width = h.GetXaxis().GetBinWidth(1)

        if first_hist_is_data :
            h.GetYaxis().SetTitle( 'Events / %.3f ' %bin_width )
        else :
            h.GetYaxis().SetTitle( 'A.U. / %.3f ' %bin_width )

    drawcmd=''
    if not first_hist_is_data :
        drawcmd += 'hist'

    if normalize :
        hists[0].DrawNormalized(drawcmd)
        drawcmd+='hist'
        for h in hists[1:] :
            h.DrawNormalized(drawcmd + 'same')
    else :
        hists[0].Draw(drawcmd)
        drawcmd+='hist'
        for h in hists[1:] :
            h.Draw(drawcmd + 'same')

    leg=None
    if legend_entries :
        drawconf = DrawConfig( None, None, None, legend_config={'legendTranslateX' : -0.1 } )
        leg = sampMan.create_standard_legend( len(hists), draw_config=drawconf )
        if added_sum_hist :
            legend_entries.append( 'Template sum' )

        for ent, hist in zip( legend_entries, hists ) :
            leg.AddEntry( hist, ent )

        leg.Draw()

    if label is not None :
        lab = ROOT.TLatex(0.12, 0.8, label )
        lab.SetTextSize( 0.04 )
        lab.SetNDC()
        lab.SetX(0.15)
        lab.SetY(0.8)
        lab.Draw()

    if logy :
        can.SetLogy()


    if outputName is None :
        raw_input('continue')
        
    if outputName is not None and not _DISABLE_TEMPLATE_SAVE :
        if not os.path.isdir( os.path.dirname(outputName) ) :
            os.makedirs( os.path.dirname(outputName) )

        can.SaveAs( outputName )

class RunNominalCalculation() :

    def __init__( self, **kwargs ) :

        self.configs = {}
        self.status = True

        self.fitvar       = kwargs.get( 'fitvar', None )
        self.channel      = kwargs.get( 'channel', None )
        self.ffcorr       = kwargs.get('ffcorr', 'None' )
        self.subl_ptrange = kwargs.get( 'subl_ptrange', (None,None) )
        self.ptbins       = kwargs.get( 'ptbins', [15,25,40,70,1000000] )
        self.systematics  = kwargs.get( 'systematics', 'Nom' )
        self.outputDir    = kwargs.get( 'outputDir', None )
        self.eleVeto      = kwargs.get( 'eleVeto', 'PassPSV' )

        
        if self.fitvar is None :
            print 'RunNominalCalculation.init -- ERROR, fitvar is required argument'
            self.status = False
            return

        if self.channel is None :
            print 'RunNominalCalculation.init -- ERROR, channel is required argument'
            self.status = False
            return

        if self.outputDir is not None :
            if self.fitvar == 'sigmaIEIE' :
                self.outputDir = self.outputDir + '/SigmaIEIEFits/JetFakeTemplateFitPlotsNomIso/%s' %self.channel
            elif self.fitvar == 'chIsoCorr' :
                self.outputDir = self.outputDir + '/ChHadIsoFits/JetFakeTemplateFitPlotsNomIso/%s' %self.channel
            elif self.fitvar == 'neuIsoCorr' :
                self.outputDir = self.outputDir + '/NeuHadIsoFits/JetFakeTemplateFitPlotsNomIso/%s' %self.channel
            elif self.fitvar == 'phoIsoCorr' :
                self.outputDir = self.outputDir + '/PhoIsoFits/JetFakeTemplateFitPlotsNomIso/%s' %self.channel
        

    def ConfigHists(self, **kwargs ) :

        if not self.status :
            print 'RunNominalCalculation.ConfigHists -- ERROR, aborting because of previous errors'

        fitvar = self.fitvar
        ch = self.channel
        ffcorr = self.ffcorr

        self.template_name_base = 'nom__templates__ffcorr_%s__%s__%s' %(ffcorr, fitvar, ch )
        self.data_name_base = 'nom__data__ffcorr_%s__%s__%s' %( ffcorr, fitvar, ch )
        self.corr_name_base = 'nom__fftemplates__ffcorr_%s__%s__%s' %(ffcorr, fitvar, ch )

        binning = get_default_binning(fitvar)
        samples = get_default_samples(ch)

        # generate templates for both EB and EE
        # do not pass ele veto -- templates should be the same 
        real_template_str = get_real_template_draw_commands(fitvar, ch ) 
        fake_template_str = get_fake_template_draw_commands(fitvar, ch ) 

        count_var, phstr = get_template_draw_strs( fitvar, ch, eleVeto='NoEleVeto', iso_vals=None )


        #print '******************************************FIX DATA TEMPLATES*************************'
        self.configs.update(config_single_photon_template(real_template_str, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__real__EB', sampMan=sampManLG))
        self.configs.update(config_single_photon_template(real_template_str, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__real__EE', sampMan=sampManLG))
        #self.configs.update(config_single_photon_template(real_template_str, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__real__EB', sampMan=sampManLLG))
        #self.configs.update(config_single_photon_template(real_template_str, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__real__EE', sampMan=sampManLLG))
        self.configs.update(config_single_photon_template(fake_template_str, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__fake__EB', sampMan=sampManLLG))
        self.configs.update(config_single_photon_template(fake_template_str, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_base+'__fake__EE', sampMan=sampManLLG))

        # get correlated fake-fake templates
        corr_template_str_leadFail_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=False, cuts=ffcorr )
        corr_template_str_leadPass_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=True , cuts=ffcorr )
        corr_template_str_leadFail_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=False, cuts=ffcorr )
        corr_template_str_leadPass_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=True , cuts=ffcorr )
        corr_template_str_leadFail_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=False, cuts=ffcorr )
        corr_template_str_leadPass_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=True , cuts=ffcorr )


            
        sampManFF = sampManDataFF
        samp_name = 'Muon'
        # Use muon channel for FF templates always
        #if ch.count( 'invpixlead' ) : 
        #    sampManFF=sampManDataInvL
        #    samp_name = 'Electron'
        #elif ch.count( 'invpixsubl' ) : 
        #    sampManFF=sampManDataInvS
        #    samp_name = 'Electron'
        #else :
        #    sampManFF = sampManDataFF
        #    samp_name = 'Muon'

        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EB', sampMan=sampManFF  ) )
        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EB', sampMan=sampManFF  ) )
        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EE, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EE', sampMan=sampManFF  ) )
        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EE, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EE', sampMan=sampManFF  ) )
        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EE_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EE-EB', sampMan=sampManFF  ) )
        self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EE_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EE-EB', sampMan=sampManFF  ) )

        # add regions onto the selection

        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB')]
        for reg in regions :
            # depreicated since update to new variables
            #if fitvar == 'sigmaIEIE' :
            #    gg_selection = get_default_draw_commands(ch) + ' && %s >1 &&  is%s_leadph12 && is%s_sublph12 ' %( count_var, reg[0], reg[1] )
            #    gg_selection_leadPass = gg_selection + ' && sieie_leadph12 < %f ' %( _sieie_cuts[reg[0]][0] )
            #    gg_selection_leadFail = gg_selection + ' && sieie_leadph12 > %f && sieie_leadph12 < %f' %( _sieie_cuts[reg[0]] )
            #elif fitvar == 'chIsoCorr' :
            #    gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passNeuIsoCorrMedium[0]==1 && ph_passPhoIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passNeuIsoCorrMedium[1]==1 && ph_passPhoIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
            #    gg_selection_leadPass = gg_selection + ' && chIsoCorr_leadph12 < %f ' %( _chIso_cuts[reg[0]][0] )
            #    gg_selection_leadFail = gg_selection + ' && chIsoCorr_leadph12 > %f && chIsoCorr_leadph12 < %f ' %( _chIso_cuts[reg[0]] )
            #elif fitvar == 'neuIsoCorr' :
            #    gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passChIsoCorrMedium[0]==1 && ph_passPhoIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passChIsoCorrMedium[1]==1 && ph_passPhoIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
            #    gg_selection_leadPass = gg_selection + ' && neuIsoCorr_leadph12 < %f ' %( _neuIso_cuts[reg[0]][0] )
            #    gg_selection_leadFail = gg_selection + ' && neuIsoCorr_leadph12 > %f && neuIsoCorr_leadph12 < %f ' %( _neuIso_cuts[reg[0]] )
            #elif fitvar == 'phoIsoCorr' :
            #    gg_selection = get_default_draw_commands(ch) + ' && ph_n>1 && ph_passSIEIEMedium[0]==1 && ph_passChIsoCorrMedium[0]==1 && ph_passNeuIsoCorrMedium[0]==1 && ph_HoverE12[0] < 0.05 && ph_passSIEIEMedium[1]==1 && ph_passChIsoCorrMedium[1]==1 && ph_passNeuIsoCorrMedium[1]==1 && ph_HoverE12[1] < 0.05 && is%s_leadph12 && is%s_sublph12 ' %( reg[0], reg[1] )
            #    gg_selection_leadPass = gg_selection + ' && phoIsoCorr_leadph12 < %f ' %( _phoIso_cuts[reg[0]][0] )
            #    gg_selection_leadFail = gg_selection + ' && phoIsoCorr_leadph12 > %f && phoIsoCorr_leadph12 < %f ' %( _phoIso_cuts[reg[0]] )

            count_var_gg = count_var
            phstr_gg = phstr

            #if count_var_gg == 'ph_mediumNoSIEIENoChIso_n' :
            #    count_var_gg = 'ph_mediumNoSIEIENoChIsoNoEleVeto_n'
            #if phstr_gg == 'ptSorted_ph_mediumNoSIEIENoChIso_idx' :
            #    phstr_gg = 'ptSorted_ph_mediumNoSIEIENoChIsoNoEleVeto_idx'
            

            gg_selection = get_default_draw_commands(ch) + ' && %s >1 &&  ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( count_var_gg, reg[0], phstr_gg, reg[1], phstr_gg )
            gg_selection_leadPass = gg_selection + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][0] )
            gg_selection_leadFail = gg_selection + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f' %(fitvar, phstr_gg,  _var_cuts[fitvar][reg[0]][0], fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][1] )
            # depreicated since update to new variables
            ## add subl pt cuts onto the selection
            #if self.subl_ptrange[0] is not None :
            #    if self.subl_ptrange[1] is None :
            #        gg_selection_leadPass = gg_selection_leadPass + ' && pt_sublph12 > %d' %self.subl_ptrange[0]
            #        gg_selection_leadFail = gg_selection_leadFail + ' && pt_sublph12 > %d' %self.subl_ptrange[0]
            #    else :
            #        gg_selection_leadPass = gg_selection_leadPass + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(self.subl_ptrange[0], self.subl_ptrange[1] )
            #        gg_selection_leadFail = gg_selection_leadFail + ' && pt_sublph12 > %d && pt_sublph12 < %d' %(self.subl_ptrange[0], self.subl_ptrange[1] )

            # add subl pt cuts onto the selection
            if self.subl_ptrange[0] is not None :
                if self.subl_ptrange[1] is None :
                    gg_selection_leadPass = gg_selection_leadPass + ' && ph_pt[%s[1]] > %d' %( phstr_gg, self.subl_ptrange[0])
                    gg_selection_leadFail = gg_selection_leadFail + ' && ph_pt[%s[1]] > %d' %( phstr_gg, self.subl_ptrange[0])
                else :
                    gg_selection_leadPass = gg_selection_leadPass + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr_gg, self.subl_ptrange[0], phstr_gg, self.subl_ptrange[1] )
                    gg_selection_leadFail = gg_selection_leadFail + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr_gg, self.subl_ptrange[0], phstr_gg, self.subl_ptrange[1] )

            # parse out the x and y binning
            ybinn = binning[reg[1]]
            xbinn = binning[reg[0]]

            # depreicated since update to new variables
            ## variable given to TTree.Draw
            #if fitvar == 'sigmaIEIE' :
            #    var = 'pt_leadph12:sieie_sublph12' #z:y:x
            #elif fitvar == 'chIsoCorr' :
            #    var = 'pt_leadph12:chIsoCorr_sublph12' #z:y:x
            #elif fitvar == 'neuIsoCorr' :
            #    var = 'pt_leadph12:neuIsoCorr_sublph12' #z:y:x
            #elif fitvar == 'phoIsoCorr' :
            #    var = 'pt_leadph12:phoIsoCorr_sublph12' #z:y:x

            var = 'ph_pt[%s[0]]:ph_%s[%s[1]]' %( phstr_gg, fitvar, phstr_gg ) #z:y:x

            print 'USE var ', var

            self.targetSampMan = sampManData
            if ch.count('invpixlead' ) :
                print 'USE sampManDataInvL'
                self.targetSampMan = sampManDataInvL
            elif ch.count('invpixsubl' ) :
                print 'USE sampManDataInvS'
                self.targetSampMan = sampManDataInvS
            elif ch.count( 'mu' ) :
                print 'USE sampManDataNOEV'
                self.targetSampMan = sampManDataNOEV
            else :
                print 'USE sampManData'
                self.targetSampMan = sampManData


            target_samp = self.targetSampMan.get_samples(name=samples['target'])
            print '---------------------------------'
            print ' Config Data                       '
            print gg_selection_leadPass
            print ' Config Data                       '
            print gg_selection_leadFail
            print '---------------------------------'
            self.configs[self.data_name_base+'__leadPass__%s-%s'%(reg[0],reg[1])] = config_and_queue_hist( target_samp[0], var, gg_selection_leadPass, ( ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=self.targetSampMan )
            self.configs[self.data_name_base+'__leadFail__%s-%s'%(reg[0],reg[1])] = config_and_queue_hist( target_samp[0], var, gg_selection_leadFail, ( ybinn[0], ybinn[1], ybinn[2], 100, 0, 500),useSampMan=self.targetSampMan )

        print self.configs

        return self.configs.values()
        
    def execute( self, **kwargs ):

        print self.configs

        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB')]
        for reg in regions :
            templates = {'lead' :{'real' : {}, 'fake' : {} }, 'subl' : {'real' : {}, 'fake' : {} } }

            #print '************************FIX DATA TEMPLATES******************************'
            templates['lead']['real'] = load_template_histograms( self.configs,'%s__real__%s' %(self.template_name_base, reg[0]) , sampManLG )
            templates['subl']['real'] = load_template_histograms( self.configs,'%s__real__%s' %(self.template_name_base, reg[1]) , sampManLG )
            #templates['lead']['real'] = load_template_histograms( self.configs,'%s__real__%s' %(self.template_name_base, reg[0]) , sampManLLG )
            #templates['subl']['real'] = load_template_histograms( self.configs,'%s__real__%s' %(self.template_name_base, reg[1]) , sampManLLG )

            templates['lead']['fake'] = load_template_histograms( self.configs,'%s__fake__%s' %(self.template_name_base, reg[0]) , sampManLLG )
            templates['subl']['fake'] = load_template_histograms( self.configs,'%s__fake__%s' %(self.template_name_base, reg[1]) , sampManLLG )

            templates_corr = None
            if self.ffcorr != 'None' :
                sampManFF = sampManDataFF
                # Use muon channel for FF templates always
                #if self.channel.count( 'invpixlead' ) : 
                #    sampManFF=sampManDataInvL
                #elif self.channel.count( 'invpixsubl' ) : 
                #    sampManFF=sampManDataInvS
                #else :
                #    sampManFF = sampManDataFF
                templates_corr = {'leadPass' : { reg : { 'Data' : None, 'Background' : None} }, 'leadFail' : { reg : { 'Data' : None, 'Background' : None} } }
                templates_corr['leadPass'][reg]['Data'] = sampManFF.load_samples( self.configs['%s__leadPass__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist
                templates_corr['leadFail'][reg]['Data'] = sampManFF.load_samples( self.configs['%s__leadFail__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist

            gg_hist = {}
            gg_hist['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist

            run_nominal_calculation( gg_hist, templates, templates_corr, reg, self.ptbins, self.channel, self.fitvar, self.ffcorr, systematics=self.systematics, subl_ptrange=self.subl_ptrange, outputDir=self.outputDir )


#class RunAsymCalculation() :
#
#    def __init__( self, **kwargs ) :
#
#        self.configs = {}
#        self.status = True
#
#        self.vals              = kwargs.get( 'vals'              , None)
#        self.fitvar            = kwargs.get( 'fitvar'            , None )
#        self.channel           = kwargs.get( 'channel'           , None )
#        self.ffcorr            = kwargs.get( 'ffcorr'            , None )
#        self.ptbins            = kwargs.get( 'ptbins'            , [15,25,40,70,1000000] )
#        self.subl_ptrange      = kwargs.get( 'subl_ptrange'      , (None,None) )
#        self.eleVeto           = kwargs.get( 'eleVeto'           , 'PassPSV' )
#        self.outputDir         = kwargs.get('outputDir'          , None )
#        
#        if self.fitvar is None :
#            print 'RunAsymCalculation.init -- ERROR, fitvar is required argument'
#            self.status = False
#            return
#
#        if self.vals is None :
#            print 'RunAsymCalculation.init -- ERROR, loose_vals is required argument'
#            self.status = False
#            return
#
#        if self.channel is None :
#            print 'RunAsymCalculation.init -- ERROR, channel is required argument'
#            self.status = False
#            return
#
#        if self.outputDir is not None :
#            if self.fitvar == 'sigmaIEIE' :
#                self.outputDir = self.outputDir + '/SigmaIEIEFits/JetFakeTemplateFitPlots%d-%d-%dAsymIso'%(self.vals)
#            elif self.fitvar == 'chIsoCorr' :
#                self.outputDir = self.outputDir + '/ChHadIsoFits/JetFakeTemplateFitPlots%d-%d-%dAsymIso'%(self.vals)
#            elif self.fitvar == 'neuIsoCorr' :
#                self.outputDir = self.outputDir + '/NeuHadIsoFits/JetFakeTemplateFitPlots%d-%d-%dAsymIso'%(self.vals )
#            elif self.fitvar == 'phoIsoCorr' :
#                self.outputDir = self.outputDir + '/PhoIsoFits/JetFakeTemplateFitPlots%d-%d-%dAsymIso'%(self.vals )
#
#        if self.fitvar == 'sigmaIEIE' :
#            # loosened iso cuts
#            self.loose_iso_cuts = self.vals
#            self.systematics=('-'.join([str(v) for v in self.vals]))
#            #---------------------------------------------------
#
#        elif self.fitvar == 'chIsoCorr' :
#            #---------------------------------------------------
#            # for using ChHadIso templates
#            # iso cuts for isolated photons
#            # loosened iso cuts
#            self.loose_iso_cuts = (None, self.vals[1], self.vals[2] )
#            self.systematics = 'No Cut-%d-%d' %( self.vals[1], self.vals[2] )
#            #---------------------------------------------------
#
#        elif self.fitvar == 'neuIsoCorr' :
#            #---------------------------------------------------
#            # for using NeuHadIso templates
#            # iso cuts for isolated photons
#            # loosened iso cuts
#            self.loose_iso_cuts = (self.vals[0], None, self.vals[2] )
#            self.systematics = '%d-No Cut-%d' %( self.vals[0], self.vals[2] )
#            #---------------------------------------------------
#
#        elif self.fitvar == 'phoIsoCorr' :
#            #---------------------------------------------------
#            # for using NeuHadIso templates
#            # iso cuts for isolated photons
#            # loosened iso cuts
#            self.loose_iso_cuts = (self.vals[0], self.vals[1], None )
#            self.systematics = '%d-%d-No Cut' %( self.vals[0], self.vals[1] )
#            #---------------------------------------------------
#
#        
#
#    def ConfigHists(self, **kwargs ) :
#
#        if not self.status :
#            print 'RunAsymCalculation.ConfigHists -- ERROR, aborting because of previous errors'
#
#        fitvar = self.fitvar
#        ch = self.channel
#        ffcorr = self.ffcorr
#
#        asym_name = 'asym-%s-%s-%s' %( self.vals )
#        
#
#        self.template_name_iso_base = '%s_templates_iso_ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
#        self.template_name_noiso_base = '%s_templates_noiso_ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
#        self.data_name_base = '%s__data__ffcorr_%s__%s__%s'%( asym_name, ffcorr, fitvar, ch )
#        self.corr_name_base = '%s__fftemplates__ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
#
#        binning = get_default_binning(fitvar)
#        samples = get_default_samples(ch)
#
#        # do not pass eleVeto
#        #real_template_str_iso = get_real_template_draw_commands(fitvar, ch, self.eleVeto)
#        #fake_template_str_iso = get_fake_template_draw_commands(fitvar, ch, self.eleVeto)
#        real_template_str_iso = get_real_template_draw_commands(fitvar, ch)
#        fake_template_str_iso = get_fake_template_draw_commands(fitvar, ch)
#
#        # do not pass eleVeto
#        #real_template_str_noiso = get_real_template_draw_commands(fitvar, ch, self.eleVeto, iso_vals = self.loose_iso_cuts )
#        #fake_template_str_noiso = get_fake_template_draw_commands(fitvar, ch, self.eleVeto, iso_vals = self.loose_iso_cuts )
#        real_template_str_noiso = get_real_template_draw_commands(fitvar, ch, iso_vals = self.loose_iso_cuts )
#        fake_template_str_noiso = get_fake_template_draw_commands(fitvar, ch, iso_vals = self.loose_iso_cuts )
#
#        count_var, phstr = get_template_draw_strs( fitvar, ch, eleVeto='NoEleVeto', iso_vals=self.vals )
#
#        self.configs.update(config_single_photon_template(real_template_str_iso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__real__EB', sampMan=sampManLG ) )
#        self.configs.update(config_single_photon_template(real_template_str_iso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__real__EE', sampMan=sampManLG ) )
#        self.configs.update(config_single_photon_template(fake_template_str_iso, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__fake__EB', sampMan=sampManLLG ) )
#        self.configs.update(config_single_photon_template(fake_template_str_iso, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__fake__EE', sampMan=sampManLLG ) )
#
#        self.configs.update(config_single_photon_template(real_template_str_noiso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__real__EB', sampMan=sampManLG  ) )
#        self.configs.update(config_single_photon_template(real_template_str_noiso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__real__EE', sampMan=sampManLG  ) )
#        self.configs.update(config_single_photon_template(fake_template_str_noiso, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__fake__EB', sampMan=sampManLLG ) )
#        self.configs.update(config_single_photon_template(fake_template_str_noiso, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__fake__EE', sampMan=sampManLLG ) )
#
#        if ffcorr != 'None' :
#            corr_template_str_leadFail_EB_EB = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EB', 'EB', leadPass=False, cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#            corr_template_str_leadPass_EB_EB = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EB', 'EB', leadPass=True , cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#            corr_template_str_leadFail_EB_EE = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EB', 'EE', leadPass=False, cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#            corr_template_str_leadPass_EB_EE = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EB', 'EE', leadPass=True , cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#            corr_template_str_leadFail_EE_EB = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EE', 'EB', leadPass=False, cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#            corr_template_str_leadPass_EE_EB = get_corr_fake_template_draw_commands_with_iso( ch, fitvar, 'EE', 'EB', leadPass=True , cuts=ffcorr, iso_vals=self.loose_iso_cuts )
#
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EB', sampMan=sampManDataNOEV  ))
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EB', sampMan=sampManDataNOEV  ))
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EE', sampMan=sampManDataNOEV  ))
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EE, binning, {'Data' :'Muon', 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EE', sampMan=sampManDataNOEV  ))
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EE-EB', sampMan=sampManDataNOEV  ))
#            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EE_EB, binning, {'Data' :'Muon', 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EE-EB', sampMan=sampManDataNOEV  ))
#
#        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB') ]
#
#        for reg in regions :
#            
#            # add regions onto the selection
#            varstr, phstr = get_template_draw_strs( fitvar, ch, self.eleVeto, self.loose_iso_cuts)
#            varstr_bothiso, phstr_bothiso = get_template_draw_strs( fitvar, ch, self.eleVeto, None)
#
#            gg_selection_looseiso = get_default_draw_commands(ch) + ' && %s > 1 && ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( varstr, reg[0], phstr, reg[1], phstr )
#
#            gg_selection_iso = get_default_draw_commands(ch) + ' && %s > 1 && ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( varstr_bothiso, reg[0], phstr_bothiso, reg[1], phstr_bothiso )
#
#            # add subl pt cuts onto the selection
#            if self.subl_ptrange[0] is not None :
#                if self.subl_ptrange[1] is None :
#                    gg_selection_looseiso = gg_selection_looseiso + ' && ph_pt[%s[1]] > %d' %( phstr, self.subl_ptrange[0])
#                    gg_selection_iso      = gg_selection_iso      + ' && ph_pt[%s[1]] > %d' %( phstr, self.subl_ptrange[0])
#                else :
#                    gg_selection_looseiso = gg_selection_looseiso + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr, self.subl_ptrange[0], phstr, self.subl_ptrange[1] )
#                    gg_selection_iso      = gg_selection_iso      + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr, self.subl_ptrange[0], phstr, self.subl_ptrange[1] )
#
#            nom_iso_cuts = ''
#            for key, cuts in _var_cuts.iteritems() :
#                if key == fitvar :
#                    continue
#
#                nom_iso_cutsd += ' && ph_%s[%s[0]] < %f ' %( key, phstr, cuts[reg[0]][0] )
#
#            gg_selection_iso = gg_selection_iso + nom_iso_cuts
#
#            gg_selection_looseiso_leadPass = gg_selection_looseiso + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr, _var_cuts[fitvar][reg[0]][0] )
#            gg_selection_looseiso_leadFail = gg_selection_looseiso + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f ' %( fitvar, phstr, _var_cuts[fitvar][reg[0]][0], fitvar, phstr, _var_cuts[fitvar][reg[0]][1] )
#            gg_selection_iso_leadPass = gg_selection_iso + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr, _var_cuts[fitvar][reg[0]][0] )
#            gg_selection_iso_leadFail = gg_selection_iso + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f ' %( fitvar, phstr, _var_cuts[fitvar][reg[0]][0], fitvar, phstr, _var_cuts[fitvar][reg[0]][1]  )
#
#
#            # parse out the x and y binning
#            ybinn = binning[reg[1]]
#            xbinn = binning[reg[0]]
#            ptbinn = ( 40, 0, 200 )
#
#            # depricated since variable change
#            ## variable given to TTree.Draw
#            ##var = 'ph_pt[0]:ph_sigmaIEIE[1]:ph_sigmaIEIE[0]' #z:y:x
#            #if fitvar == 'sigmaIEIE' :
#            #    var = 'pt_leadph12:sieie_sublph12' #y:x
#            #    var_bothiso = 'pt_leadph12:sieie_sublph12' #y:x
#            #elif fitvar == 'chIsoCorr' :
#            #    var = 'pt_leadph12:chIsoCorr_sublph12' #y:x
#            #    var_bothiso = 'pt_leadph12:chIsoCorr_sublph12' #y:x
#            #elif fitvar == 'neuIsoCorr' :
#            #    var = 'pt_leadph12:neuIsoCorr_sublph12' #y:x
#            #    var_bothiso = 'pt_leadph12:neuIsoCorr_sublph12' #y:x
#            #elif fitvar == 'phoIsoCorr' :
#            #    var = 'pt_leadph12:phoIsoCorr_sublph12' #y:x
#            #    var_bothiso = 'pt_leadph12:phoIsoCorr_sublph12' #y:x
#
#            # variable given to TTree.Draw
#            #var = 'ph_pt[0]:ph_sigmaIEIE[1]:ph_sigmaIEIE[0]' #z:y:x
#            var = 'ph_pt[%s[0]]:ph_%s[%s[1]]' %( phstr, fitvar, phstr )
#            var_bothiso = 'ph_pt[%s[0]]:ph_%s[%s[1]]' %( phstr_bothiso, fitvar, phstr_bothiso )
#            # get sample
#
#            self.targetSampMan = sampManData
#
#            # for certain channels, use a different SampleManager
#            if ch.count('invpixlead' ) :
#                print 'USE sampManDataInvL'
#                self.targetSampMan = sampManDataInvL
#
#            elif ch.count('invpixsubl' ) :
#                print 'USE sampManDataInvS'
#                self.targetSampMan = sampManDataInvS
#
#            elif ch.count('mu' ) :
#                print 'USE sampManDataNOEV'
#                self.targetSampMan = sampManDataNOEV
#
#            else :
#                print 'USE sampManData'
#                self.targetSampMan = sampManData
#
#            target_samp = self.targetSampMan.get_samples(name=samples['target'])
#
#            plot_binning =  ( ybinn[0], ybinn[1], ybinn[2], ptbinn[0], ptbinn[1], ptbinn[2] )
#
#            # draw and get back the hist
#            print '---------------------------------'
#            print var
#            print ' Draw LooseIso leadPass           '
#            print gg_selection_looseiso_leadPass
#            print ' Draw LooseIso leadFail           '
#            print gg_selection_looseso_leadFail
#            print '---------------------------------'
#            self.configs[self.data_name_base+'__leadPass__looseiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_looseiso_leadPass, plot_binning,useSampMan=self.targetSampMan)
#            self.configs[self.data_name_base+'__leadFail__looseiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_looseiso_leadFail, plot_binning,useSampMan=self.targetSampMan)
#            print '---------------------------------'
#            print var
#            print ' Draw Iso leadPass           '
#            print gg_selection_iso_leadPass
#            print ' Draw Iso leadFail           '
#            print gg_selection_iso_leadFail
#            print '---------------------------------'
#            self.configs[self.data_name_base+'__leadPass__iso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_iso_leadPass, plot_binning ,useSampMan=self.targetSampMan)
#            self.configs[self.data_name_base+'__leadFail__iso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_iso_leadFail, plot_binning ,useSampMan=self.targetSampMan)
#
#        print self.configs
#
#        return self.configs.values()
#        
#    def execute( self, **kwargs ):
#
#        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB')]
#        for reg in regions :
#            templates_leadiso = {'lead' : { 'real' : {}, 'fake' : {} }, 'subl' : {'real' : {}, 'fake' : {} } }
#            templates_subliso = {'lead' : { 'real' : {}, 'fake' : {} }, 'subl' : {'real' : {}, 'fake' : {} } }
#
#            templates_leadiso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s' %(self.template_name_iso_base, reg[0]), sampManLG )
#            templates_leadiso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s' %(self.template_name_noiso_base, reg[1]), sampManLG )
#            templates_leadiso['lead']['fake'] = load_template_histograms( self.configs, '%s__fake__%s' %(self.template_name_iso_base, reg[0]), sampManLLG )
#            templates_leadiso['subl']['fake'] = load_template_histograms( self.configs, '%s__fake__%s' %(self.template_name_noiso_base, reg[1]), sampManLLG )
#
#            templates_subliso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s' %(self.template_name_noiso_base, reg[0]), sampManLG )
#            templates_subliso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s' %(self.template_name_iso_base, reg[1]), sampManLG )
#            templates_subliso['lead']['fake'] = load_template_histograms( self.configs, '%s__fake__%s' %(self.template_name_noiso_base, reg[0]), sampManLLG )
#            templates_subliso['subl']['fake'] = load_template_histograms( self.configs, '%s__fake__%s' %(self.template_name_iso_base, reg[1]), sampManLLG )
#
#            templates_nom = {}
#            templates_nom['lead'] = {}
#            templates_nom['subl'] = {}
#            templates_nom['subl']['real'] = templates_subliso['subl']['real']
#            templates_nom['subl']['fake'] = templates_subliso['subl']['fake']
#            templates_nom['lead']['real'] = templates_leadiso['lead']['real']
#            templates_nom['lead']['fake'] = templates_leadiso['lead']['fake']
#
#            templates_corr = None
#            if self.ffcorr != 'None' :
#                templates_corr = {'leadPass' : { reg : { 'Data' : None, 'Background' : None} }, 'leadFail' : { reg : { 'Data' : None, 'Background' : None} } }
#                templates_corr['leadPass'][reg]['Data'] = sampManDataNOEV.load_samples( self.configs['%s__leadPass__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist
#                templates_corr['leadFail'][reg]['Data'] = sampManDataNOEV.load_samples( self.configs['%s__leadFail__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist
#
#            gg_hist_leadiso = {}
#            gg_hist_subliso = {}
#            gg_hist_bothiso = {}
#            gg_hist_leadiso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__leadiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#            gg_hist_leadiso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__leadiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#            gg_hist_subliso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__subliso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#            gg_hist_subliso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__subliso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#            gg_hist_bothiso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__bothiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#            gg_hist_bothiso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__bothiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
#
#            run_corr_calculation( templates_leadiso, templates_subliso, templates_nom, templates_corr, gg_hist_leadiso, gg_hist_subliso, gg_hist_bothiso, reg, self.ptbins, self.channel, self.fitvar, self.ffcorr, systematics=self.systematics,subl_ptrange=self.subl_ptrange,outputDir=self.outputDir )
            
class RunCorrectedAsymCalculation() :

    def __init__( self, **kwargs ) :

        self.configs = {}
        self.status = True

        self.vals              = kwargs.get( 'vals'              , None)
        self.fitvar            = kwargs.get( 'fitvar'            , None )
        self.channel           = kwargs.get( 'channel'           , None )
        self.ffcorr            = kwargs.get( 'ffcorr'            , None )
        self.ptbins            = kwargs.get( 'ptbins'            , [15,25,40,70,1000000] )
        self.subl_ptrange      = kwargs.get( 'subl_ptrange'      , (None,None) )
        self.eleVeto           = kwargs.get( 'eleVeto'           , 'PassPSV' )
        self.addtlVar          = kwargs.get( 'addtlVar'          , None )
        self.addtlVarCut       = kwargs.get( 'addtlVarCut'          , None )
        self.outputDir         = kwargs.get('outputDir'          , None )
        
        if self.fitvar is None :
            print 'RunCorrectedAsymCalculation.init -- ERROR, fitvar is required argument'
            self.status = False
            return

        if self.vals is None :
            print 'RunCorrectedAsymCalculation.init -- ERROR, loose_vals is required argument'
            self.status = False
            return

        if self.channel is None :
            print 'RunCorrectedAsymCalculation.init -- ERROR, channel is required argument'
            self.status = False
            return

        if self.outputDir is not None :
            if isinstance( self.vals, str ) :
                vals_str = self.vals 
            elif isinstance( self.vals, tuple ) :
                vals_str = '%d-%d-%d' %(self.vals)

            if self.fitvar == 'sigmaIEIE' :
                self.outputDir = self.outputDir + '/SigmaIEIEFits/JetFakeTemplateFitPlotsCorr%sAsymIso/%s'%(vals_str, self.channel)
            elif self.fitvar == 'chIsoCorr' :
                self.outputDir = self.outputDir + '/ChHadIsoFits/JetFakeTemplateFitPlotsCorr%sAsymIso/%s'%(vals_str, self.channel)
            elif self.fitvar == 'neuIsoCorr' :
                self.outputDir = self.outputDir + '/NeuHadIsoFits/JetFakeTemplateFitPlotsCorr%sAsymIso/%s'%(vals_str, self.channel)
            elif self.fitvar == 'phoIsoCorr' :
                self.outputDir = self.outputDir + '/PhoIsoFits/JetFakeTemplateFitPlotsCorr%sAsymIso/%s'%(vals_str, self.channel)

        if self.fitvar == 'sigmaIEIE' :
            # loosened iso cuts
            self.loose_iso_cuts = self.vals
            if isinstance( self.vals, str ) :
                self.systematics = '%s-%s' %(self.fitvar, self.vals )
            else :
                self.systematics=('-'.join([str(v) for v in self.vals]))
            #---------------------------------------------------

        elif self.fitvar == 'chIsoCorr' :
            #---------------------------------------------------
            # for using ChHadIso templates
            # iso cuts for isolated photons
            # loosened iso cuts
            if isinstance( self.vals, str ) :
                self.loose_iso_cuts = self.vals
                self.systematics = '%s-%s' %(self.fitvar, self.vals )
            else :
                self.loose_iso_cuts = (None, self.vals[1], self.vals[2] )
                self.systematics = 'No Cut-%d-%d' %( self.vals[1], self.vals[2] )
            #---------------------------------------------------

        elif self.fitvar == 'neuIsoCorr' :
            #---------------------------------------------------
            # for using NeuHadIso templates
            # iso cuts for isolated photons
            # loosened iso cuts
            if isinstance( self.vals, str ) :
                self.loose_iso_cuts = self.vals
                self.systematics = '%s-%s' %(self.fitvar, self.vals )
            else :
                self.loose_iso_cuts = (self.vals[0], None, self.vals[2] )
                self.systematics = '%d-No Cut-%d' %( self.vals[0], self.vals[2] )
            #---------------------------------------------------

        elif self.fitvar == 'phoIsoCorr' :
            #---------------------------------------------------
            # for using NeuHadIso templates
            # iso cuts for isolated photons
            # loosened iso cuts
            if isinstance( self.vals, str ) :
                self.loose_iso_cuts = self.vals
                self.systematics = '%s-%s' %(self.fitvar, self.vals )
            else :
                self.loose_iso_cuts = (self.vals[0], self.vals[1], None )
                self.systematics = '%d-%d-No Cut' %( self.vals[0], self.vals[1] )
            #---------------------------------------------------

        

    def ConfigHists(self, **kwargs ) :

        if not self.status :
            print 'RunCorrectedAsymCalculation.ConfigHists -- ERROR, aborting because of previous errors'

        fitvar = self.fitvar
        ch = self.channel
        ffcorr = self.ffcorr

        if isinstance( self.vals, tuple ) :
            asym_name = 'asym-%s-%s-%s' %( self.vals )
        elif isinstance( self.vals, str) :
            asym_name = 'asym-%s' %self.vals
        

        self.template_name_iso_base = '%s_templates_iso_ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
        self.template_name_noiso_base = '%s_templates_noiso_ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
        self.data_name_base = '%s__data__ffcorr_%s__%s__%s'%( asym_name, ffcorr, fitvar, ch )
        self.corr_name_base = '%s__fftemplates__ffcorr_%s__%s__%s' %( asym_name, ffcorr, fitvar, ch )
        
        if self.addtlVar is not None and self.addtlVarCut is not None :
            self.data_name_base += '__cut_%s_%d-%d' %( self.addtlVar, self.addtlVarCut[0], self.addtlVarCut[1] )

        binning = get_default_binning(fitvar)
        samples = get_default_samples(ch)

        # do not pass eleVeto-- templates should be the same with or without ele veto
        #real_template_str_iso = get_real_template_draw_commands(fitvar, ch, self.eleVeto)
        #fake_template_str_iso = get_fake_template_draw_commands(fitvar, ch, self.eleVeto)

        real_template_str_iso_noeveto = get_real_template_draw_commands(fitvar, ch, 'NoEleVeto')
        fake_template_str_iso_noeveto = get_fake_template_draw_commands(fitvar, ch, 'NoEleVeto')
        real_template_str_iso_passPSV = get_real_template_draw_commands(fitvar, ch, 'PassPSV')
        fake_template_str_iso_passPSV = get_fake_template_draw_commands(fitvar, ch, 'PassPSV')
        real_template_str_iso_failPSV = get_real_template_draw_commands(fitvar, ch, 'FailPSV')
        fake_template_str_iso_failPSV = get_fake_template_draw_commands(fitvar, ch, 'FailPSV')

        # do not pass eleVeto -- templates should be the same with or without ele veto
        #real_template_str_noiso = get_real_template_draw_commands(fitvar, ch, self.eleVeto, iso_vals = self.loose_iso_cuts )
        #fake_template_str_noiso = get_fake_template_draw_commands(fitvar, ch, self.eleVeto, iso_vals = self.loose_iso_cuts )
        real_template_str_noiso_noeveto = get_real_template_draw_commands(fitvar, ch, 'NoEleVeto', iso_vals = self.loose_iso_cuts )
        fake_template_str_noiso_noeveto = get_fake_template_draw_commands(fitvar, ch, 'NoEleVeto', iso_vals = self.loose_iso_cuts )
        real_template_str_noiso_passPSV = get_real_template_draw_commands(fitvar, ch, 'PassPSV', iso_vals = self.loose_iso_cuts )
        fake_template_str_noiso_passPSV = get_fake_template_draw_commands(fitvar, ch, 'PassPSV', iso_vals = self.loose_iso_cuts )
        real_template_str_noiso_failPSV = get_real_template_draw_commands(fitvar, ch, 'FailPSV', iso_vals = self.loose_iso_cuts )
        fake_template_str_noiso_failPSV = get_fake_template_draw_commands(fitvar, ch, 'FailPSV', iso_vals = self.loose_iso_cuts )

        count_var_iso_NoEleVeto, phstr_iso_NoEleVeto = get_template_draw_strs( fitvar, ch, eleVeto='NoEleVeto', iso_vals=None )
        count_var_iso_PassPSV  , phstr_iso_PassPSV   = get_template_draw_strs( fitvar, ch, eleVeto='PassPSV'  , iso_vals=None )
        count_var_iso_FailPSV  , phstr_iso_FailPSV   = get_template_draw_strs( fitvar, ch, eleVeto='FailPSV'  , iso_vals=None )

        count_var_noiso_NoEleVeto, phstr_noiso_NoEleVeto = get_template_draw_strs( fitvar, ch, eleVeto='NoEleVeto', iso_vals=self.vals )
        count_var_noiso_PassPSV  , phstr_noiso_PassPSV   = get_template_draw_strs( fitvar, ch, eleVeto='PassPSV'  , iso_vals=self.vals )
        count_var_noiso_FailPSV  , phstr_noiso_FailPSV   = get_template_draw_strs( fitvar, ch, eleVeto='FailPSV'  , iso_vals=self.vals )
        #count_var, phstr = get_template_draw_strs( fitvar, ch, eleVeto=eleVeto, iso_vals=self.vals )

        sampManReal = sampManLG
        #if ch.count( 'invpix' ) :
        #    sampManReal = sampManInvReal


        #print '************************FIX DATA TEMPLATES******************************'
        self.configs.update(config_single_photon_template(real_template_str_iso_noeveto, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_iso_NoEleVeto, basename=self.template_name_iso_base+'__real__NoEleVeto__EB', sampMan=sampManReal ) )
        self.configs.update(config_single_photon_template(real_template_str_iso_noeveto, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_iso_NoEleVeto, basename=self.template_name_iso_base+'__real__NoEleVeto__EE', sampMan=sampManReal ) )
        self.configs.update(config_single_photon_template(real_template_str_iso_passPSV, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_iso_PassPSV, basename=self.template_name_iso_base+'__real__PassPSV__EB', sampMan=sampManReal ) )
        self.configs.update(config_single_photon_template(real_template_str_iso_passPSV, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_iso_PassPSV, basename=self.template_name_iso_base+'__real__PassPSV__EE', sampMan=sampManReal ) )
        self.configs.update(config_single_photon_template(real_template_str_iso_failPSV, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_iso_FailPSV, basename=self.template_name_iso_base+'__real__FailPSV__EB', sampMan=sampManReal ) )
        self.configs.update(config_single_photon_template(real_template_str_iso_failPSV, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_iso_FailPSV, basename=self.template_name_iso_base+'__real__FailPSV__EE', sampMan=sampManReal ) )
        #self.configs.update(config_single_photon_template(real_template_str_iso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__real__EB', sampMan=sampManLLG ) )
        #self.configs.update(config_single_photon_template(real_template_str_iso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_iso_base+'__real__EE', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_noeveto, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_iso_NoEleVeto, basename=self.template_name_iso_base+'__fake__NoEleVeto__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_noeveto, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_iso_NoEleVeto, basename=self.template_name_iso_base+'__fake__NoEleVeto__EE', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_passPSV, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_iso_PassPSV, basename=self.template_name_iso_base+'__fake__PassPSV__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_passPSV, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_iso_PassPSV, basename=self.template_name_iso_base+'__fake__PassPSV__EE', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_failPSV, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_iso_FailPSV, basename=self.template_name_iso_base+'__fake__FailPSV__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_iso_failPSV, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_iso_FailPSV, basename=self.template_name_iso_base+'__fake__FailPSV__EE', sampMan=sampManLLG ) )

        #print '************************FIX DATA TEMPLATES******************************'
        self.configs.update(config_single_photon_template(real_template_str_noiso_noeveto, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_NoEleVeto, basename=self.template_name_noiso_base+'__real__NoEleVeto__EB', sampMan=sampManReal  ) )
        self.configs.update(config_single_photon_template(real_template_str_noiso_noeveto, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_NoEleVeto, basename=self.template_name_noiso_base+'__real__NoEleVeto__EE', sampMan=sampManReal  ) )
        self.configs.update(config_single_photon_template(real_template_str_noiso_passPSV, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_PassPSV, basename=self.template_name_noiso_base+'__real__PassPSV__EB', sampMan=sampManReal  ) )
        self.configs.update(config_single_photon_template(real_template_str_noiso_passPSV, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_PassPSV, basename=self.template_name_noiso_base+'__real__PassPSV__EE', sampMan=sampManReal  ) )
        self.configs.update(config_single_photon_template(real_template_str_noiso_failPSV, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_FailPSV, basename=self.template_name_noiso_base+'__real__FailPSV__EB', sampMan=sampManReal  ) )
        self.configs.update(config_single_photon_template(real_template_str_noiso_failPSV, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_FailPSV, basename=self.template_name_noiso_base+'__real__FailPSV__EE', sampMan=sampManReal  ) )
        #self.configs.update(config_single_photon_template(real_template_str_noiso, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__real__EB', sampMan=sampManLLG  ) )
        #self.configs.update(config_single_photon_template(real_template_str_noiso, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr, basename=self.template_name_noiso_base+'__real__EE', sampMan=sampManLLG  ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_noeveto, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_NoEleVeto, basename=self.template_name_noiso_base+'__fake__NoEleVeto__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_noeveto, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_NoEleVeto, basename=self.template_name_noiso_base+'__fake__NoEleVeto__EE', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_passPSV, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_PassPSV, basename=self.template_name_noiso_base+'__fake__PassPSV__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_passPSV, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_PassPSV, basename=self.template_name_noiso_base+'__fake__PassPSV__EE', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_failPSV, binning['EB'], samples['fake'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_FailPSV, basename=self.template_name_noiso_base+'__fake__FailPSV__EB', sampMan=sampManLLG ) )
        self.configs.update(config_single_photon_template(fake_template_str_noiso_failPSV, binning['EE'], samples['fake'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_FailPSV, basename=self.template_name_noiso_base+'__fake__FailPSV__EE', sampMan=sampManLLG ) )

        if ch.count( 'invpix' ) :

            count_var_iso_DY, phstr_iso_DY = get_template_draw_strs( fitvar, ch, eleVeto='FailPSV', iso_vals=None )
            count_var_noiso_DY, phstr_noiso_DY = get_template_draw_strs( fitvar, ch, eleVeto='FailPSV', iso_vals=self.vals )

            real_template_str_iso_DY = get_real_template_draw_commands(fitvar, ch, 'FailPSV', dy=True)
            real_template_str_noiso_DY = get_real_template_draw_commands(fitvar, ch, 'FailPSV', iso_vals = self.loose_iso_cuts, dy=True)

            self.configs.update(config_single_photon_template(real_template_str_iso_DY, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_iso_DY, basename=self.template_name_iso_base+'__real__DY__EB', sampMan=sampManInvReal ) )
            self.configs.update(config_single_photon_template(real_template_str_iso_DY, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_iso_DY, basename=self.template_name_iso_base+'__real__DY__EE', sampMan=sampManInvReal ) )
            
            self.configs.update(config_single_photon_template(real_template_str_noiso_DY, binning['EB'], samples['real'], 'EB', fitvar=fitvar, idxstr=phstr_noiso_DY, basename=self.template_name_noiso_base+'__real__DY__EB', sampMan=sampManInvReal ) )
            self.configs.update(config_single_photon_template(real_template_str_noiso_DY, binning['EE'], samples['real'], 'EE', fitvar=fitvar, idxstr=phstr_noiso_DY, basename=self.template_name_noiso_base+'__real__DY__EE', sampMan=sampManInvReal ) )


        if ffcorr != 'None' :
            corr_template_str_leadFail_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=False, cuts=ffcorr )
            corr_template_str_leadPass_EB_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EB', leadPass=True , cuts=ffcorr )
            corr_template_str_leadFail_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=False, cuts=ffcorr )
            corr_template_str_leadPass_EB_EE = get_corr_fake_template_draw_commands( ch, fitvar, 'EB', 'EE', leadPass=True , cuts=ffcorr )
            corr_template_str_leadFail_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=False, cuts=ffcorr )
            corr_template_str_leadPass_EE_EB = get_corr_fake_template_draw_commands( ch, fitvar, 'EE', 'EB', leadPass=True , cuts=ffcorr )

            sampManFF = sampManDataFF
            samp_name = 'Muon'
            # Use muon channel for FF templates always
            #if ch.count( 'invpixlead' ) : 
            #    print 'sampManFF=sampManDataInvL'
            #    samp_name = 'Electron'
            #    sampManFF=sampManDataInvL
            #elif ch.count( 'invpixsubl' ) : 
            #    print 'sampManFF=sampManDataInvS'
            #    sampManFF=sampManDataInvS
            #    samp_name = 'Electron'
            #else :
            #    print 'sampManFF = sampManDataFF'
            #    sampManFF = sampManDataFF
            #    samp_name = 'Muon'
 

            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EB', sampMan=sampManFF  ))
            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EB', sampMan=sampManFF  ))
            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EB_EE, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EB-EE', sampMan=sampManFF  ))
            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EB_EE, binning, {'Data' :samp_name, 'Background' : None }, 'EB', 'EE', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EB-EE', sampMan=sampManFF  ))
            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadFail_EE_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadFail__EE-EB', sampMan=sampManFF  ))
            self.configs.update(config_correlated_fake_fake_templates( corr_template_str_leadPass_EE_EB, binning, {'Data' :samp_name, 'Background' : None }, 'EE', 'EB', fitvar=fitvar, basename=self.corr_name_base+'__leadPass__EE-EB', sampMan=sampManFF  ))

        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB') ]

        for reg in regions :
            
            # add regions onto the selection
            varstr, phstr = get_template_draw_strs( fitvar, ch, self.eleVeto, self.loose_iso_cuts)
            if ch.count('invpix') : 
                varstr_bothiso, phstr_bothiso = get_template_draw_strs( fitvar, ch, 'NoEleVeto', None)
            else :
                varstr_bothiso, phstr_bothiso = get_template_draw_strs( fitvar, ch, self.eleVeto, None)
            # remove after the varibles are available

            varstr_gg = varstr
            varstr_bothiso_gg = varstr_bothiso
            phstr_gg = phstr
            phstr_bothiso_gg = phstr_bothiso

            #if varstr_gg == 'ph_mediumNoSIEIENoChIso_n' :
            #    varstr_gg = 'ph_mediumNoSIEIENoChIsoNoEleVeto_n'
            #if varstr_bothiso_gg == 'ph_mediumNoSIEIENoChIso_n' :
            #    varstr_bothiso_gg = 'ph_mediumNoSIEIENoChIsoNoEleVeto_n'
            #if phstr_gg == 'ptSorted_ph_mediumNoSIEIENoChIso_idx' :
            #    phstr_gg = 'ptSorted_ph_mediumNoSIEIENoChIsoNoEleVeto_idx'
            #if phstr_bothiso_gg == 'ptSorted_ph_mediumNoSIEIENoChIso_idx' :
            #    phstr_bothiso_gg = 'ptSorted_ph_mediumNoSIEIENoChIsoNoEleVeto_idx'
            
            gg_selection_leadiso = get_default_draw_commands(ch) + ' && %s > 1 && ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( varstr_gg, reg[0], phstr_gg, reg[1], phstr_gg )
            gg_selection_subliso = get_default_draw_commands(ch) + ' && %s > 1 && ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( varstr_gg, reg[0], phstr_gg, reg[1], phstr_gg )

            gg_selection_bothiso = get_default_draw_commands(ch) + ' && %s > 1 && ph_Is%s[%s[0]] && ph_Is%s[%s[1]] ' %( varstr_bothiso_gg, reg[0], phstr_bothiso_gg, reg[1], phstr_bothiso_gg )

            if self.addtlVar is not None and self.addtlVarCut is not None :
                addtl_var_str = ' && %s > %d && %s < %d '  %( self.addtlVar, self.addtlVarCut[0], self.addtlVar, self.addtlVarCut[1] )

                gg_selection_bothiso += addtl_var_str
                gg_selection_leadiso += addtl_var_str
                gg_selection_subliso += addtl_var_str

            # add subl pt cuts onto the selection
            if self.subl_ptrange[0] is not None :
                if self.subl_ptrange[1] is None :
                    gg_selection_leadiso = gg_selection_leadiso + ' && ph_pt[%s[1]] > %d' %( phstr_gg, self.subl_ptrange[0])
                    gg_selection_subliso = gg_selection_subliso + ' && ph_pt[%s[1]] > %d' %( phstr_gg, self.subl_ptrange[0])
                    gg_selection_bothiso = gg_selection_bothiso + ' && ph_pt[%s[1]] > %d' %( phstr_bothiso_gg, self.subl_ptrange[0])
                else :
                    gg_selection_leadiso = gg_selection_leadiso + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr_gg, self.subl_ptrange[0], phstr_gg, self.subl_ptrange[1] )
                    gg_selection_subliso = gg_selection_subliso + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr_gg, self.subl_ptrange[0], phstr_gg, self.subl_ptrange[1] )
                    gg_selection_bothiso = gg_selection_bothiso + ' && ph_pt[%s[1]] > %d && ph_pt[%s[1]] < %d' %(phstr_bothiso_gg, self.subl_ptrange[0], phstr_bothiso_gg, self.subl_ptrange[1] )

            nom_iso_cuts_lead = ''
            nom_iso_cuts_subl = ''
            for key, cuts in _var_cuts.iteritems() :
                if key == fitvar :
                    continue

                nom_iso_cuts_lead += ' && ph_%s[%s[0]] < %f ' %( key, phstr_gg, cuts[reg[0]][0] )
                nom_iso_cuts_subl += ' && ph_%s[%s[1]] < %f ' %( key, phstr_gg, cuts[reg[1]][0] )

            gg_selection_leadiso = gg_selection_leadiso + nom_iso_cuts_lead 
            gg_selection_subliso = gg_selection_subliso + nom_iso_cuts_subl 

            gg_selection_leadiso_leadPass = gg_selection_leadiso + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][0] )
            gg_selection_leadiso_leadFail = gg_selection_leadiso + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f ' %( fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][0], fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][1] )
            gg_selection_subliso_leadPass = gg_selection_subliso + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][0] )
            gg_selection_subliso_leadFail = gg_selection_subliso + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f ' %( fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][0], fitvar, phstr_gg, _var_cuts[fitvar][reg[0]][1]  )

            gg_selection_bothiso_leadPass = gg_selection_bothiso + ' && ph_%s[%s[0]] < %f ' %( fitvar, phstr_bothiso_gg, _var_cuts[fitvar][reg[0]][0] )
            gg_selection_bothiso_leadFail = gg_selection_bothiso + ' && ph_%s[%s[0]] > %f && ph_%s[%s[0]] < %f ' %( fitvar, phstr_bothiso_gg, _var_cuts[fitvar][reg[0]][0], fitvar, phstr_bothiso_gg, _var_cuts[fitvar][reg[0]][1] )


            # parse out the x and y binning
            ybinn = binning[reg[1]]
            xbinn = binning[reg[0]]
            ptbinn = ( 40, 0, 200 )

            # depricated since variable change
            ## variable given to TTree.Draw
            ##var = 'ph_pt[0]:ph_sigmaIEIE[1]:ph_sigmaIEIE[0]' #z:y:x
            #if fitvar == 'sigmaIEIE' :
            #    var = 'pt_leadph12:sieie_sublph12' #y:x
            #    var_bothiso = 'pt_leadph12:sieie_sublph12' #y:x
            #elif fitvar == 'chIsoCorr' :
            #    var = 'pt_leadph12:chIsoCorr_sublph12' #y:x
            #    var_bothiso = 'pt_leadph12:chIsoCorr_sublph12' #y:x
            #elif fitvar == 'neuIsoCorr' :
            #    var = 'pt_leadph12:neuIsoCorr_sublph12' #y:x
            #    var_bothiso = 'pt_leadph12:neuIsoCorr_sublph12' #y:x
            #elif fitvar == 'phoIsoCorr' :
            #    var = 'pt_leadph12:phoIsoCorr_sublph12' #y:x
            #    var_bothiso = 'pt_leadph12:phoIsoCorr_sublph12' #y:x

            # variable given to TTree.Draw
            #var = 'ph_pt[0]:ph_sigmaIEIE[1]:ph_sigmaIEIE[0]' #z:y:x
            var = 'ph_pt[%s[0]]:ph_%s[%s[1]]' %( phstr_gg, fitvar, phstr_gg )
            var_bothiso = 'ph_pt[%s[0]]:ph_%s[%s[1]]' %( phstr_bothiso_gg, fitvar, phstr_bothiso_gg )
            # get sample

            self.targetSampMan = sampManData

            # for certain channels, use a different SampleManager
            if ch.count('invpixlead' ) :
                print 'USE sampManDataInvL'
                self.targetSampMan = sampManDataInvL

            elif ch.count('invpixsubl' ) :
                print 'USE sampManDataInvS'
                self.targetSampMan = sampManDataInvS

            elif ch.count('mu' ) :
                print 'USE sampManDataNOEV'
                self.targetSampMan = sampManDataNOEV

            else :
                print 'USE sampManData'
                self.targetSampMan = sampManData

            target_samp = self.targetSampMan.get_samples(name=samples['target'])

            plot_binning =  ( ybinn[0], ybinn[1], ybinn[2], ptbinn[0], ptbinn[1], ptbinn[2] )

            # draw and get back the hist
            print '---------------------------------'
            print var
            print ' Draw LeadIso leadPass           '
            print gg_selection_leadiso_leadPass
            print ' Draw LeadIso leadFail           '
            print gg_selection_leadiso_leadFail
            print '---------------------------------'
            self.configs[self.data_name_base+'__leadPass__leadiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_leadiso_leadPass, plot_binning,useSampMan=self.targetSampMan)
            self.configs[self.data_name_base+'__leadFail__leadiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_leadiso_leadFail, plot_binning,useSampMan=self.targetSampMan)
            print '---------------------------------'
            print var
            print ' Draw SublIso leadPass           '
            print gg_selection_subliso_leadPass
            print ' Draw SublIso leadFail           '
            print gg_selection_subliso_leadFail
            print '---------------------------------'
            self.configs[self.data_name_base+'__leadPass__subliso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_subliso_leadPass, plot_binning ,useSampMan=self.targetSampMan)
            self.configs[self.data_name_base+'__leadFail__subliso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var, gg_selection_subliso_leadFail, plot_binning ,useSampMan=self.targetSampMan)
            print '---------------------------------'
            print var
            print ' Draw BothIso leadPass           '
            print gg_selection_bothiso_leadPass
            print ' Draw BothIso leadFail           '
            print gg_selection_bothiso_leadFail
            print '---------------------------------'
            self.configs[self.data_name_base+'__leadPass__bothiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var_bothiso, gg_selection_bothiso_leadPass, plot_binning,useSampMan=self.targetSampMan)
            self.configs[self.data_name_base+'__leadFail__bothiso__%s-%s' %(reg)] = config_and_queue_hist( target_samp[0], var_bothiso, gg_selection_bothiso_leadFail, plot_binning,useSampMan=self.targetSampMan)

        print self.configs

        return self.configs.values()
        
    def execute( self, **kwargs ):

        regions = [ ('EB', 'EB'), ('EB', 'EE'), ('EE', 'EB')]
        for reg in regions :
            templates_leadiso = {'lead' : { 'real' : {}, 'fake' : {} }, 'subl' : {'real' : {}, 'fake' : {} } }
            templates_subliso = {'lead' : { 'real' : {}, 'fake' : {} }, 'subl' : {'real' : {}, 'fake' : {} } }

            leadEVetoReal = 'NoEleVeto'
            sublEVetoReal = 'NoEleVeto'
            leadEVetoFake = 'NoEleVeto'
            sublEVetoFake = 'NoEleVeto'

            #if self.channel.count('el') and not self.channel.count('Zgg') :

            if self.channel.count('invpixlead') :
                leadEVetoReal = 'DY'
                leadEVetoFake = 'FailPSV'
                sublEVetoReal = 'PassPSV'
                sublEVetoFake = 'PassPSV'
                #sublEVetoReal = 'NoEleVeto'
                #sublEVetoFake = 'NoEleVeto'
               
            if self.channel.count( 'invpixsubl' ) :
                sublEVetoReal = 'DY'
                sublEVetoFake = 'FailPSV'
                leadEVetoReal = 'PassPSV'
                leadEVetoFake = 'PassPSV'
                #leadEVetoReal = 'NoEleVeto'
                #leadEVetoFake = 'NoEleVeto'


            if self.channel.count('el') and not self.channel.count('Zgg') and not self.channel.count('invpix') :
                leadEVetoReal = 'PassPSV'
                sublEVetoReal = 'PassPSV'
                leadEVetoFake = 'PassPSV'
                sublEVetoFake = 'PassPSV'

            sampManRealLead = sampManLG
            sampManRealSubl = sampManLG
            if self.channel.count( 'invpixlead' ) :
                sampManRealLead = sampManInvReal
            if self.channel.count( 'invpixsubl' ) :
                sampManRealSubl = sampManInvReal


            #print '************************FIX DATA TEMPLATES******************************'
            templates_leadiso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_iso_base, leadEVetoReal, reg[0]), sampManRealLead )
            templates_leadiso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_noiso_base, sublEVetoReal, reg[1]), sampManRealSubl )
            #templates_leadiso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_iso_base, leadEVeto,reg[0]), sampManLLG )
            #templates_leadiso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_noiso_base, sublEVeto, reg[1]), sampManLLG )
            templates_leadiso['lead']['fake'] = load_template_histograms( self.configs, '%s__fake__%s__%s' %(self.template_name_iso_base, leadEVetoFake, reg[0]), sampManLLG )
            templates_leadiso['subl']['fake'] = load_template_histograms( self.configs, '%s__fake__%s__%s' %(self.template_name_noiso_base, sublEVetoFake, reg[1]), sampManLLG )

            #print '************************FIX DATA TEMPLATES******************************'
            templates_subliso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_noiso_base, leadEVetoReal, reg[0]), sampManRealLead )
            templates_subliso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_iso_base, sublEVetoReal, reg[1]), sampManRealSubl )
            #templates_subliso['lead']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_noiso_base, leadEVeto, reg[0]), sampManLLG )
            #templates_subliso['subl']['real'] = load_template_histograms( self.configs, '%s__real__%s__%s' %(self.template_name_iso_base, sublEVeto, reg[1]), sampManLLG )
            templates_subliso['lead']['fake'] = load_template_histograms( self.configs, '%s__fake__%s__%s' %(self.template_name_noiso_base, leadEVetoFake, reg[0]), sampManLLG )
            templates_subliso['subl']['fake'] = load_template_histograms( self.configs, '%s__fake__%s__%s' %(self.template_name_iso_base, sublEVetoFake, reg[1]), sampManLLG )

            templates_nom = {}
            templates_nom['lead'] = {}
            templates_nom['subl'] = {}
            templates_nom['subl']['real'] = templates_subliso['subl']['real']
            templates_nom['subl']['fake'] = templates_subliso['subl']['fake']
            templates_nom['lead']['real'] = templates_leadiso['lead']['real']
            templates_nom['lead']['fake'] = templates_leadiso['lead']['fake']

            templates_corr = None
            if self.ffcorr != 'None' :
                sampManFF = sampManDataFF
                # Use muon channel for FF templates always
                #if self.channel.count( 'invpixlead' ) : 
                #    print 'sampManFF=sampManDataInvL'
                #    sampManFF=sampManDataInvL
                #elif self.channel.count( 'invpixsubl' ) : 
                #    print 'sampManFF=sampManDataInvS'
                #    sampManFF=sampManDataInvS
                #else :
                #    print 'sampManFF = sampManDataFF'
                #    sampManFF = sampManDataFF

                templates_corr = {'leadPass' : { reg : { 'Data' : None, 'Background' : None} }, 'leadFail' : { reg : { 'Data' : None, 'Background' : None} } }
                templates_corr['leadPass'][reg]['Data'] = sampManFF.load_samples( self.configs['%s__leadPass__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist
                templates_corr['leadFail'][reg]['Data'] = sampManFF.load_samples( self.configs['%s__leadFail__%s-%s__Data' %( self.corr_name_base, reg[0], reg[1] )] )[0].hist

            gg_hist_leadiso = {}
            gg_hist_subliso = {}
            gg_hist_bothiso = {}
            gg_hist_leadiso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__leadiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist_leadiso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__leadiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist_subliso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__subliso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist_subliso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__subliso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist_bothiso['leadPass'] = self.targetSampMan.load_samples( self.configs['%s__leadPass__bothiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist
            gg_hist_bothiso['leadFail'] = self.targetSampMan.load_samples( self.configs['%s__leadFail__bothiso__%s-%s' %(self.data_name_base, reg[0], reg[1])] )[0].hist

            calcPostfix = ''
            if self.addtlVar is not None and self.addtlVarCut is not None :
                calcPostfix = '__cut_%s_%d-%d' %( self.addtlVar, self.addtlVarCut[0], self.addtlVarCut[1] )

            run_corr_calculation( templates_leadiso, templates_subliso, templates_nom, templates_corr, gg_hist_leadiso, gg_hist_subliso, gg_hist_bothiso, reg, self.ptbins, self.channel, self.fitvar, self.ffcorr, systematics=self.systematics,subl_ptrange=self.subl_ptrange,outputDir=self.outputDir, calcPostfix=calcPostfix )
            
def config_single_photon_template( selection, binning, sample, reg, fitvar='sigmaIEIE', idxstr='', basename='', sampMan=None) :

    if sampMan is None :
        sampMan = sampManLG

    if reg not in ['EB', 'EE'] :
        print 'Region not specified correctly'
        return None

    var = 'ph_pt[%s[0]]:ph_%s[%s[0]]' %(idxstr, fitvar, idxstr) #y:x


    selection = selection + ' && ph_Is%s[%s[0]] ' %( reg, idxstr)

    data_samp_name = sample['Data']
    bkg_samp_name  = sample.get('Background', None)

    template_configs = {}


    data_samp = sampMan.get_samples(name=data_samp_name )

    if data_samp :
        print '---------------------------------'
        print ' Draw Template for var %s        ' %fitvar
        print 'Binning = ', binning
        print selection
        print '---------------------------------'
    
        template_configs[basename+'__Data'] = config_and_queue_hist( data_samp[0], var, selection, ( binning[0], binning[1], binning[2],100, 0, 500  ), useSampMan=sampMan ) 
    else :
        print 'Data template sample not found!'
        
    if bkg_samp_name is not None :
        bkg_samp = sampMan.get_samples(name=bkg_samp_name )

        if bkg_samp :
            print '---------------------------------'
            print ' Draw Template Background for var %s ' %fitvar
            print selection
            print '---------------------------------'
            template_configs[basename+'__Background'] = config_and_queue_hist( bkg_samp[0], var, selection, ( binning[0], binning[1], binning[2],100, 0, 500  ), useSampMan=sampMan ) 
        else :
            print 'Background template sample not found!'
    else :
        template_configs[basename+'__Background']=None

    return template_configs

def config_correlated_fake_fake_templates( selection, binning, sample, reg1, reg2, fitvar='sigmaIEIE', basename='', sampMan=None) :

    if sampMan is None :
        sampMan = sampManLG

    if reg1 not in ['EB', 'EE'] or reg2 not in ['EB', 'EE'] :
        print 'Region not specified correctly'
        return None

    fitvarmod = ''
    if fitvar == 'sigmaIEIE' :
        fitvarmod = 'sieie'
    else :
        fitvarmod = fitvar

    var = 'pt_leadph12:%s_sublph12' %(fitvarmod)#y:x

    selection = selection + ' && is%s_leadph12 && is%s_sublph12 ' %( reg1, reg2 )

    data_samp_name = sample['Data']
    bkg_samp_name  = sample.get('Background', None)

    template_configs = {}

    data_samp = sampMan.get_samples(name=data_samp_name )

    if data_samp :
        print '---------------------------------'
        print ' Draw 2-D correlated Template for var %s        ' %fitvar
        print 'Binning = ', ( binning[reg2][0], binning[reg2][1], binning[reg2][2], 100, 0, 500  )
        print selection
        print '---------------------------------'
    
        template_configs[basename+'__Data'] = config_and_queue_hist( data_samp[0], var, selection, ( binning[reg2][0], binning[reg2][1], binning[reg2][2], 100, 0, 500  ), useSampMan=sampMan ) 
    else :
        print 'Data template sample not found!'
        
    template_configs[basename+'__Background']=None

    return template_configs

def load_template_histograms( configs, name_base, sampMan ) :

    templates = {'Data' : None, 'Background' : None }

    templates['Data'] = sampMan.load_samples( configs['%s__Data' %(name_base)] )[0].hist
    if configs['%s__Background' %(name_base)] is None :
        templates['Background'] = None
    else :
        templates['Background'] = sampMan.load_samples( configs['%s__Background' %(name_base) ] )[0].hist

    return templates


if __name__ == '__main__' :
    options = parseArgs()
    if options.outputDir is not None :
        ROOT.gROOT.SetBatch(True)
    else :
        ROOT.gROOT.SetBatch(False)
    
    if options.ptbins is not None :
        common_ptbins = [int(x) for x in options.ptbins.split(',')]

    main()

    #print 'Number of matrx calls = %d' %_nmatrix_calls
