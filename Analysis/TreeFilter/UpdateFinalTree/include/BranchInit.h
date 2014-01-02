#ifndef BRANCHINIT_H
#define BRANCHINIT_H
#include "TTree.h"
#include "TChain.h"
void InitINTree( TChain * tree );
void InitOUTTree( TTree * tree );
void CopyInputVarsToOutput(std::string prefix = std::string() );
void CopyPrefixBranchesInToOut( const std::string & prefix );
void CopyPrefixIndexBranchesInToOut( const std::string & prefix, unsigned index );
void ClearOutputPrefix ( const std::string & prefix );
void CopynVtxBSInToOut( std::string prefix = std::string() ); 
void CopypfMETInToOut( std::string prefix = std::string() ); 
void CopypfMETPhiInToOut( std::string prefix = std::string() ); 
void CopypfMETsumEtInToOut( std::string prefix = std::string() ); 
void CopypfMETmEtSigInToOut( std::string prefix = std::string() ); 
void CopypfMETSigInToOut( std::string prefix = std::string() ); 
void CopyrecoPfMETInToOut( std::string prefix = std::string() ); 
void CopyrecoPfMETPhiInToOut( std::string prefix = std::string() ); 
void CopyrecoPfMETsumEtInToOut( std::string prefix = std::string() ); 
void CopyrecoPfMETmEtSigInToOut( std::string prefix = std::string() ); 
void CopyrecoPfMETSigInToOut( std::string prefix = std::string() ); 
void Copyel_nInToOut( std::string prefix = std::string() ); 
void Copymu_nInToOut( std::string prefix = std::string() ); 
void Copyph_nInToOut( std::string prefix = std::string() ); 
void Copyph_sl_nInToOut( std::string prefix = std::string() ); 
void Copyjet_nInToOut( std::string prefix = std::string() ); 
void Copyvtx_nInToOut( std::string prefix = std::string() ); 
void Copyel_ptInToOut( std::string prefix = std::string() ); 
void Copyel_ptInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_pt( std::string prefix ); 
void Copyel_etaInToOut( std::string prefix = std::string() ); 
void Copyel_etaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_eta( std::string prefix ); 
void Copyel_scetaInToOut( std::string prefix = std::string() ); 
void Copyel_scetaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_sceta( std::string prefix ); 
void Copyel_phiInToOut( std::string prefix = std::string() ); 
void Copyel_phiInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_phi( std::string prefix ); 
void Copyel_eInToOut( std::string prefix = std::string() ); 
void Copyel_eInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_e( std::string prefix ); 
void Copyel_mvaInToOut( std::string prefix = std::string() ); 
void Copyel_mvaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_mva( std::string prefix ); 
void Copyel_d0pvInToOut( std::string prefix = std::string() ); 
void Copyel_d0pvInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_d0pv( std::string prefix ); 
void Copyel_z0pvInToOut( std::string prefix = std::string() ); 
void Copyel_z0pvInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_z0pv( std::string prefix ); 
void Copyel_sigmaIEIEInToOut( std::string prefix = std::string() ); 
void Copyel_sigmaIEIEInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_sigmaIEIE( std::string prefix ); 
void Copyel_pfiso30InToOut( std::string prefix = std::string() ); 
void Copyel_pfiso30InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_pfiso30( std::string prefix ); 
void Copyel_hasMatchedConvInToOut( std::string prefix = std::string() ); 
void Copyel_hasMatchedConvInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_hasMatchedConv( std::string prefix ); 
void Copyel_passTightInToOut( std::string prefix = std::string() ); 
void Copyel_passTightInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_passTight( std::string prefix ); 
void Copyel_passMediumInToOut( std::string prefix = std::string() ); 
void Copyel_passMediumInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_passMedium( std::string prefix ); 
void Copyel_passLooseInToOut( std::string prefix = std::string() ); 
void Copyel_passLooseInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_passLoose( std::string prefix ); 
void Copyel_passVeryLooseInToOut( std::string prefix = std::string() ); 
void Copyel_passVeryLooseInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_passVeryLoose( std::string prefix ); 
void Copyel_passTightTrigInToOut( std::string prefix = std::string() ); 
void Copyel_passTightTrigInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_passTightTrig( std::string prefix ); 
void Copyel_truthMatch_phInToOut( std::string prefix = std::string() ); 
void Copyel_truthMatch_phInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_truthMatch_ph( std::string prefix ); 
void Copyel_truthMatchInToOut( std::string prefix = std::string() ); 
void Copyel_truthMatchInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_truthMatch( std::string prefix ); 
void Copyel_truthMinDRInToOut( std::string prefix = std::string() ); 
void Copyel_truthMinDRInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputel_truthMinDR( std::string prefix ); 
void Copymu_ptInToOut( std::string prefix = std::string() ); 
void Copymu_ptInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_pt( std::string prefix ); 
void Copymu_etaInToOut( std::string prefix = std::string() ); 
void Copymu_etaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_eta( std::string prefix ); 
void Copymu_phiInToOut( std::string prefix = std::string() ); 
void Copymu_phiInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_phi( std::string prefix ); 
void Copymu_eInToOut( std::string prefix = std::string() ); 
void Copymu_eInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_e( std::string prefix ); 
void Copymu_pfIso_chInToOut( std::string prefix = std::string() ); 
void Copymu_pfIso_chInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_pfIso_ch( std::string prefix ); 
void Copymu_pfIso_nhInToOut( std::string prefix = std::string() ); 
void Copymu_pfIso_nhInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_pfIso_nh( std::string prefix ); 
void Copymu_pfIso_phoInToOut( std::string prefix = std::string() ); 
void Copymu_pfIso_phoInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_pfIso_pho( std::string prefix ); 
void Copymu_pfIso_puInToOut( std::string prefix = std::string() ); 
void Copymu_pfIso_puInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_pfIso_pu( std::string prefix ); 
void Copymu_corrIsoInToOut( std::string prefix = std::string() ); 
void Copymu_corrIsoInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_corrIso( std::string prefix ); 
void Copymu_truthMatchInToOut( std::string prefix = std::string() ); 
void Copymu_truthMatchInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_truthMatch( std::string prefix ); 
void Copymu_truthMinDRInToOut( std::string prefix = std::string() ); 
void Copymu_truthMinDRInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputmu_truthMinDR( std::string prefix ); 
void Copyph_ptInToOut( std::string prefix = std::string() ); 
void Copyph_ptInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_pt( std::string prefix ); 
void Copyph_etaInToOut( std::string prefix = std::string() ); 
void Copyph_etaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_eta( std::string prefix ); 
void Copyph_phiInToOut( std::string prefix = std::string() ); 
void Copyph_phiInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_phi( std::string prefix ); 
void Copyph_eInToOut( std::string prefix = std::string() ); 
void Copyph_eInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_e( std::string prefix ); 
void Copyph_HoverEInToOut( std::string prefix = std::string() ); 
void Copyph_HoverEInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_HoverE( std::string prefix ); 
void Copyph_sigmaIEIEInToOut( std::string prefix = std::string() ); 
void Copyph_sigmaIEIEInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sigmaIEIE( std::string prefix ); 
void Copyph_chIsoCorrInToOut( std::string prefix = std::string() ); 
void Copyph_chIsoCorrInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_chIsoCorr( std::string prefix ); 
void Copyph_neuIsoCorrInToOut( std::string prefix = std::string() ); 
void Copyph_neuIsoCorrInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_neuIsoCorr( std::string prefix ); 
void Copyph_phoIsoCorrInToOut( std::string prefix = std::string() ); 
void Copyph_phoIsoCorrInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_phoIsoCorr( std::string prefix ); 
void Copyph_eleVetoInToOut( std::string prefix = std::string() ); 
void Copyph_eleVetoInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_eleVeto( std::string prefix ); 
void Copyph_isConvInToOut( std::string prefix = std::string() ); 
void Copyph_isConvInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_isConv( std::string prefix ); 
void Copyph_conv_nTrkInToOut( std::string prefix = std::string() ); 
void Copyph_conv_nTrkInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_nTrk( std::string prefix ); 
void Copyph_conv_vtx_xInToOut( std::string prefix = std::string() ); 
void Copyph_conv_vtx_xInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_vtx_x( std::string prefix ); 
void Copyph_conv_vtx_yInToOut( std::string prefix = std::string() ); 
void Copyph_conv_vtx_yInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_vtx_y( std::string prefix ); 
void Copyph_conv_vtx_zInToOut( std::string prefix = std::string() ); 
void Copyph_conv_vtx_zInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_vtx_z( std::string prefix ); 
void Copyph_conv_ptin1InToOut( std::string prefix = std::string() ); 
void Copyph_conv_ptin1InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_ptin1( std::string prefix ); 
void Copyph_conv_ptin2InToOut( std::string prefix = std::string() ); 
void Copyph_conv_ptin2InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_ptin2( std::string prefix ); 
void Copyph_conv_ptout1InToOut( std::string prefix = std::string() ); 
void Copyph_conv_ptout1InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_ptout1( std::string prefix ); 
void Copyph_conv_ptout2InToOut( std::string prefix = std::string() ); 
void Copyph_conv_ptout2InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_conv_ptout2( std::string prefix ); 
void Copyph_passTightInToOut( std::string prefix = std::string() ); 
void Copyph_passTightInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_passTight( std::string prefix ); 
void Copyph_passMediumInToOut( std::string prefix = std::string() ); 
void Copyph_passMediumInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_passMedium( std::string prefix ); 
void Copyph_passLooseInToOut( std::string prefix = std::string() ); 
void Copyph_passLooseInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_passLoose( std::string prefix ); 
void Copyph_truthMatch_phInToOut( std::string prefix = std::string() ); 
void Copyph_truthMatch_phInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_truthMatch_ph( std::string prefix ); 
void Copyph_truthMatch_elInToOut( std::string prefix = std::string() ); 
void Copyph_truthMatch_elInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_truthMatch_el( std::string prefix ); 
void Copyph_truthMatch_muInToOut( std::string prefix = std::string() ); 
void Copyph_truthMatch_muInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_truthMatch_mu( std::string prefix ); 
void Copyph_truthMatch_qInToOut( std::string prefix = std::string() ); 
void Copyph_truthMatch_qInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_truthMatch_q( std::string prefix ); 
void Copyph_sl_ptInToOut( std::string prefix = std::string() ); 
void Copyph_sl_ptInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_pt( std::string prefix ); 
void Copyph_sl_etaInToOut( std::string prefix = std::string() ); 
void Copyph_sl_etaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_eta( std::string prefix ); 
void Copyph_sl_phiInToOut( std::string prefix = std::string() ); 
void Copyph_sl_phiInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_phi( std::string prefix ); 
void Copyph_sl_eInToOut( std::string prefix = std::string() ); 
void Copyph_sl_eInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_e( std::string prefix ); 
void Copyph_sl_d0InToOut( std::string prefix = std::string() ); 
void Copyph_sl_d0InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_d0( std::string prefix ); 
void Copyph_sl_z0InToOut( std::string prefix = std::string() ); 
void Copyph_sl_z0InToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_z0( std::string prefix ); 
void Copyph_sl_convfitInToOut( std::string prefix = std::string() ); 
void Copyph_sl_convfitInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_convfit( std::string prefix ); 
void Copyph_sl_misshitsInToOut( std::string prefix = std::string() ); 
void Copyph_sl_misshitsInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputph_sl_misshits( std::string prefix ); 
void Copyjet_ptInToOut( std::string prefix = std::string() ); 
void Copyjet_ptInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputjet_pt( std::string prefix ); 
void Copyjet_etaInToOut( std::string prefix = std::string() ); 
void Copyjet_etaInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputjet_eta( std::string prefix ); 
void Copyjet_phiInToOut( std::string prefix = std::string() ); 
void Copyjet_phiInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputjet_phi( std::string prefix ); 
void Copyjet_eInToOut( std::string prefix = std::string() ); 
void Copyjet_eInToOutIndex( unsigned index, std::string prefix = std::string() ); 
void ClearOutputjet_e( std::string prefix ); 
void CopyavgPUInToOut( std::string prefix = std::string() ); 
void CopyisBlindedInToOut( std::string prefix = std::string() ); 
void CopyleadPhot_ptInToOut( std::string prefix = std::string() ); 
void CopysublPhot_ptInToOut( std::string prefix = std::string() ); 
void CopyleadPhot_lepDRInToOut( std::string prefix = std::string() ); 
void CopysublPhot_lepDRInToOut( std::string prefix = std::string() ); 
void Copyph_phDRInToOut( std::string prefix = std::string() ); 
void CopyphPhot_lepDRInToOut( std::string prefix = std::string() ); 
void CopyleadPhot_lepDPhiInToOut( std::string prefix = std::string() ); 
void CopysublPhot_lepDPhiInToOut( std::string prefix = std::string() ); 
void Copyph_phDPhiInToOut( std::string prefix = std::string() ); 
void CopyphPhot_lepDPhiInToOut( std::string prefix = std::string() ); 
void Copymt_lep_metInToOut( std::string prefix = std::string() ); 
void Copymt_lepph1_metInToOut( std::string prefix = std::string() ); 
void Copymt_lepph2_metInToOut( std::string prefix = std::string() ); 
void Copymt_lepphph_metInToOut( std::string prefix = std::string() ); 
void Copym_leplepInToOut( std::string prefix = std::string() ); 
void Copym_lepph1InToOut( std::string prefix = std::string() ); 
void Copym_lepph2InToOut( std::string prefix = std::string() ); 
void Copym_leplepphInToOut( std::string prefix = std::string() ); 
void Copym_lepphphInToOut( std::string prefix = std::string() ); 
void Copym_phphInToOut( std::string prefix = std::string() ); 
void Copym_leplepZInToOut( std::string prefix = std::string() ); 
void Copym_3lepInToOut( std::string prefix = std::string() ); 
void Copym_4lepInToOut( std::string prefix = std::string() ); 
void Copypt_leplepInToOut( std::string prefix = std::string() ); 
void Copypt_lepph1InToOut( std::string prefix = std::string() ); 
void Copypt_lepph2InToOut( std::string prefix = std::string() ); 
void Copypt_lepphphInToOut( std::string prefix = std::string() ); 
void Copypt_leplepphInToOut( std::string prefix = std::string() ); 
void Copypt_secondLeptonInToOut( std::string prefix = std::string() ); 
void Copypt_thirdLeptonInToOut( std::string prefix = std::string() ); 
#endif