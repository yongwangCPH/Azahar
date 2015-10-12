from __future__ import division
import pymol
from pymol import cmd
import numpy as np
import threading
import glob, os, sys
path = os.path.dirname(__file__)
sys.path.append(path)
from torsionals import *
from utils import pose_from_pdb, get_glyco_bonds, writer
 
def mcm_run(pose, mc_steps, SASA, randomize):
    try:
        import openbabel as ob
        t = threading.Thread(target=mcm, args=(pose, mc_steps, SASA, randomize))
        t.daemon = True # XXX
        t.start()
    except ImportError:
        import tkMessageBox
        tkMessageBox.showerror(message='In order to run MCM, you need to have openbabel installed in your system. Read http://pymolwiki.org/index.php/Azahar for more information', title='openbabel not found')
        

def sample_uniform(pose, con_matrix, angles_prob):
    random_angle = np.random.choice(['phi', 'psi', 'chi'], p=angles_prob)
    random_res = np.random.random_integers(0, len(con_matrix)-1)
    bond = con_matrix[random_res]
    cmd.copy('tmp', pose)
    if random_angle == "phi":
        phi = get_phi('tmp', bond)
        angle_value = np.random.normal(phi, 30)
        set_phi('tmp', bond, angle_value)
    elif random_angle == "psi":
        psi = get_psi('tmp', bond)
        angle_value = np.random.normal(psi, 30)
        set_psi('tmp', bond, angle_value)
    else:
        set_chi('tmp', bond)
        set_chi('tmp', bond)


def sample_fromfile(pose, con_matrix, angles_prob):
    pass


def mcm(pose, mc_steps, SASA, randomize):
    print 'Starting MCM'
    from energy import minimize, set_sasa, get_sasa
    cmd.set('suspend_updates', 'on')
    cmd.feedback('disable', 'executive', 'everything')   ##uncomment for debugging
    cmd.set('pdb_conect_all', 1)
    ################################# MCM Parameters ##########################
    T = 300. # Temperature 
    k = 0.0019872041 # Boltzmann constant
    angles_prob = [1/3, 1/3, 1/3] # probability to sample phi, psi or chi
    accepted = 0
    ############################################################################
    # 
    first, last = pose_from_pdb(pose)
    glyco_bonds = get_glyco_bonds(first, last)
    con_matrix = writer(glyco_bonds)
    
    # Remove previous pdb files
    prev_files = glob.glob('mcm_*.pdb')
    for prev_file in prev_files:
        os.remove(prev_file)
    
    # set all paramenters for sasa-energy computation
    if SASA:
        params, points, const = set_sasa(n=1000)
    ## randomize initial conformation
    if randomize:
        for i in range(len(con_matrix)-1):
            bond = con_matrix[i]
            angle_values = np.random.uniform(-180, 180, size=2)
            set_psi(pose, bond, angle_values[0])
            set_phi(pose, bond, angle_values[1])
            for i in range(6):
                set_chi(pose, bond)
    
    # minimize energy of starting conformation and save it
    NRG_old = minimize(pose, nsteps=5000, rigid_geometry=False)
    cmd.save('mcm_%08d.pdb' % accepted)

    ## start MCM routine
    fd = open("mcm_log.txt", "w")
    print '# iterations remaining = %s' % (mc_steps)
    for i in range(1, mc_steps+1):
        if i % (mc_steps//10) == 0:
            print '#remaining iterations = %s' % (mc_steps-i)
        if True:
            sample_uniform(pose, con_matrix, angles_prob)
        NRG_new = minimize('tmp', nsteps=100, rigid_geometry=False)
        if SASA:
            solvatation_nrg = get_sasa(params, points, const, selection='all',
             probe=0)[0]
            NRG_new = NRG_new + solvatation_nrg
        if NRG_new < NRG_old:
            NRG_old = NRG_new 
            fd.write('%8d%10.2f\n' % (accepted, NRG_new))
            cmd.copy(pose, 'tmp')
            cmd.delete('tmp')
            cmd.save('mcm_%08d.pdb' % accepted)
            accepted += 1
        else:
            delta = np.exp(-(NRG_new-NRG_old)/(T*k))
            if delta > np.random.uniform(0, 1):
                NRG_old = NRG_new
                fd.write('%8d%10.2f\n' % (accepted, NRG_new))

                cmd.copy(pose, 'tmp')
                cmd.delete('tmp')
                cmd.save('mcm_%08d.pdb' % accepted)
                accepted += 1
        cmd.delete('tmp')
    fd.close()

    cmd.delete('all')
    print 'Savings all accepted conformations on a single file'
    cmd.set('defer_builds_mode', 5)
    for i in range(0, accepted):
        cmd.load('mcm_%08d.pdb' % i, 'mcm_trace')
    cmd.save('mcm_trace.pdb', 'all', state=0)
    cmd.delete('all')
    cmd.load('mcm_trace.pdb')
    cmd.intra_fit('mcm_trace')
    print ' MCM completed'
    cmd.set('suspend_updates', 'off')
    
