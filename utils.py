"""
Functions to compute several glycan properties
The currently available functions are:
Radius of gyration
Ramachandran plot
"""
from __future__ import division  
import pymol
from pymol import cmd, stored
import numpy as np
import matplotlib.pyplot as plt
import tkMessageBox
from pymol.cgo import *
import os, sys
path = os.path.dirname(__file__)
sys.path.append(path)
#from torsionals import get_phi, get_psi

def analyse(type_analysis, selection, from_state, to_state,  visual, by_state):
    if type_analysis == 'Rama scatter':
        rama_plot(selection, from_state, to_state, scatter=True)
    elif type_analysis == 'Rama hex':
        rama_plot(selection, from_state, to_state, scatter=False)
    elif type_analysis == ' Rg':
        r_gyration(selection, from_state, to_state,  visual, by_state)
    elif type_analysis == ' Hydro pairs':
        hydro_pairs(selection)

def pose_from_pdb(pdb_file):
    """
    Obtain residue indexes 
    """
    stored.ResiduesNumber = []
    cmd.iterate('name c1', 'stored.ResiduesNumber.append((resi))')
    if stored.ResiduesNumber:
        first = int(stored.ResiduesNumber[0])
        last = first+len(stored.ResiduesNumber)
        return first, last
    else:
        tkMessageBox.showerror("GlycanNotFound", "There is no glycan molecule \
or the atoms in your molecule have a non-standard nomenclature")
        return None, None
    
    
def get_glyco_bonds(first, last):
    """
    Obtain glycosidic bonds from a pymol object
    """       
    stored.nb = []
    for res_i in range(first, last):
        # TODO In the future we should be able to deal with glyco-conjugates!
        cmd.iterate( "not polymer and (neighbor resi %s)" % res_i,  
        'stored.nb.append((%s, int(resi), name[-1], resn))' % res_i)
    return stored.nb
    

def writer(bonds):
    """
    Write conectivity matrix
    """
    con_matrix = []
    for i, ibond in enumerate(bonds):
        for jbond in bonds[i+1:]:
            if ibond[0] == jbond[1] and ibond[1] == jbond[0]:
                con_matrix.append((jbond[0], jbond[3], ibond[0],
                 ibond[3], int(ibond[2]), int(jbond[2])))        
    return con_matrix


def r_gyration(selection='all', from_state=1, to_state=1,  visual=True, by_state=True):
    """
    Calculates radius of gyration for a PyMOL object
    
    Arguments:
    -------------------------------------------------
    selection: key word. Selects and object 
    from_state: int. First state to calculate RG
    to_state: int. Last state to calculate RG
    visual: boolean. 
    by_state: boolean.
    """
    fd = open('Rg.dat', 'w')
    radii = []
    centers = []
    for state in range(from_state, to_state+1):
        model = cmd.get_model(selection, state)
        xyz = np.array(model.get_coord_list())
        center = np.average(xyz, 0)
        centers.append(center)
        rg = np.sqrt(np.sum((xyz - center)**2)/len(xyz))
        fd.write('%9d%8.2f\n'% (state, rg))
        radii.append(rg)
    try:     
        rg_mean = sum(radii)/len(radii)
        centers_mean = sum(centers)/len(centers)
    except ZeroDivisionError:
        rg_mean = np.nan
        centers_mean = np.nan
    fd.write('Rg_mean = %8.2f\n'% rg_mean)   
    fd.close()
    print 'Rg_mean = %8.2f\n' % rg_mean

    if visual:
        r, g, b = 0, 0, 1
        if by_state:
            cmd.set('defer_updates', 'on')
            for state in range(from_state, to_state+1):
                x1, y1, z1 = tuple(centers[state-1])
                radius = radii[state-1]
                obj = [COLOR, r, g, b, SPHERE, x1, y1, z1, radius]
                cmd.load_cgo(obj,'sphere_rg', state+1)
            cmd.set('defer_updates', 'off')
        else:
            x1, y1, z1 = tuple(centers_mean)
            radius = rg_mean
            obj = [COLOR, r, g, b, SPHERE, x1, y1, z1, radius]
            cmd.load_cgo(obj,'sphere_rg')


def rama_plot(selection='all', from_state=1, to_state=1, scatter=True):
    """ 
    Makes a scatter plot with the phi and psi angle pairs
    """
    first, last = pose_from_pdb(selection)
    if first or last:
        bonds = get_glyco_bonds(first, last)
    
        con_matrix = writer(bonds)
    
        phi = []
        psi = []
        for state in range(from_state, to_state+1):
            for element in con_matrix:
                phi.append(get_phi(selection, element, state))
                psi.append(get_psi(selection, element, state))

        if scatter:
            plt.scatter(phi, psi)
        else:
            gridsize=100
            #gridsize = int(2*len(phi)**(1/3))
            #if gridsize < 36:
            #    gridsize = 36
            plt.hexbin(phi, psi, gridsize=gridsize, cmap=plt.cm.summer, mincnt=1)
    
        plt.xlabel('$\phi$', fontsize=16)
        plt.ylabel('$\psi$', fontsize=16, rotation=0)
        plt.xlim(-180, 180) 
        plt.ylim(-180, 180)
        plt.show()
        
def hydro_pairs(selection):
    """
    Find hydrogen bonds for a given selection
    
    """
    states=cmd.count_states(selection)                 
    for i in range(1, states+1):        
        hb.append(cmd.find_pairs("(byres %s) and (name O* and neighbor elem H) or (name N* and neighbor elem H)"%(selection), 
                                 "(byres %s) and name N* or name O*"%(selection),  
                                cutoff = 3.5, mode =1, angle=40, state1=i))              
    hb.sort()
    seen = {}
    for state in hb:        
        for pairs in state:            
            if pairs in seen:
                seen[pairs] = seen[pairs] + 1
            else:
                seen[pairs] = 1                           
    occurrence = seen.items()
    occurrence.sort(key=lambda x:x[1], reverse=True)
    
    fd=open("Hydrogen pairs.txt", "w")
    
    fd.write("--------------------------------------------------------------------\n")
    fd.write("-----------------------------Results--------------------------------\n")
    fd.write("--------------------------------------------------------------------\n")
    fd.write("            Donor             |            Aceptor           |\n")
    fd.write("   Object  Residue  Atom Index|   Object  Residue  Atom Index| occurrence\n")
    
    stored.donors = []
    stored.aceptors = []
    
    for i in range (len(occurrence)):
        
        cmd.iterate("index %s"%(occurrence[i][0][0][1]), 
                    "stored.donors.append((resn, elem))")
                    
        cmd.iterate("index %s"%(occurrence[i][0][1][1]), 
                    "stored.aceptors.append((resn, elem))")
        
        
        fd.write( "%8s%8s%6s%8s|%8s%8s%6s%8s|%5s\n"%(occurrence[i][0][0][0],
                                 stored.donors[i][0],
                                 stored.donors[i][1],
                                 occurrence[i][0][0][1],
                                 occurrence[i][0][1][0],
                                 stored.aceptors[i][0],
                                 stored.aceptors[i][1],
                                 occurrence[i][0][1][1],
                                 occurrence[i][1]))
    fd.close()

