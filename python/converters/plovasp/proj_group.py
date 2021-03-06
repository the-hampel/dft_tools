 
################################################################################
#
# TRIQS: a Toolbox for Research in Interacting Quantum Systems
#
# Copyright (C) 2011 by M. Ferrero, O. Parcollet
#
# DFT tools: Copyright (C) 2011 by M. Aichhorn, L. Pourovskii, V. Vildosola
#
# PLOVasp: Copyright (C) 2015 by O. E. Peil
#
# TRIQS is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# TRIQS is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# TRIQS. If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
r"""
    vasp.proj_group
    ===============

    Storage and manipulation of projector groups.
"""
import numpy as np

np.set_printoptions(suppress=True)

################################################################################
################################################################################
#
# class ProjectorGroup
#
################################################################################
################################################################################
class ProjectorGroup:
    """
    Container of projectors defined within a certain energy window.

    The constructor selects a subset of projectors according to
    the parameters from the config-file (passed in `pars`).

    Parameters:

    - gr_pars (dict) : group parameters from the config-file
    - shells ([ProjectorShell]) : array of ProjectorShell objects
    - eigvals (numpy.array) : array of KS eigenvalues

    """
    def __init__(self, gr_pars, shells, eigvals):
        """
        Constructor
        """
        self.emin, self.emax = gr_pars['ewindow']
        self.ishells = gr_pars['shells']
        self.ortho = gr_pars['normalize']
        self.normion = gr_pars['normion']

        self.shells = shells

# Determine the minimum and maximum band numbers
        ib_win, ib_min, ib_max = self.select_bands(eigvals)
        self.ib_win = ib_win
        self.ib_min = ib_min
        self.ib_max = ib_max
        self.nb_max = ib_max - ib_min + 1

# Select projectors within the energy window
        for ish in self.ishells:
            shell = self.shells[ish]
            shell.select_projectors(ib_win, ib_min, ib_max)

        

################################################################################
#
# nelect_window
#
################################################################################
    def nelect_window(self, el_struct):
        """
        Determines the total number of electrons within the window.
        """
        self.nelect = 0
        nk, ns_band, _ = self.ib_win.shape
        rspin = 2.0 if ns_band == 1 else 1.0
        for isp in xrange(ns_band):
            for ik in xrange(nk):
                ib1 = self.ib_win[ik, isp, 0]
                ib2 = self.ib_win[ik, isp, 1]+1
                occ = el_struct.ferw[isp, ik, ib1:ib2]
                kwght = el_struct.kmesh['kweights'][ik]
                self.nelect += occ.sum() * kwght * rspin

        return self.nelect

################################################################################
#
# orthogonalize
#
################################################################################
    def orthogonalize(self):
        """
        Orthogonalize a group of projectors.

        There are two options for orthogonalizing projectors:
          1. one ensures orthogonality on each site (NORMION = True);
          2. one ensures orthogonality for subsets of sites (NORMION = False),
             as, e.g., in cluster calculations.

        In order to handle various cases the strategy is first to build a
        mapping that selects appropriate blocks of raw projectors, forms a
        matrix consisting of these blocks, orthogonalize the matrix, and use
        the mapping again to write the orthogonalized projectors back to the
        projector arrays. Note that the blocks can comprise several projector arrays
        contained in different projector shells.

        The construction of block maps is performed in 'self.get_block_matrix_map()'.
        """
# Quick exit if no normalization is requested
        if not self.ortho:
            return

        block_maps, ndim = self.get_block_matrix_map()

        _, ns, nk, _, _ = self.shells[0].proj_win.shape
        p_mat = np.zeros((ndim, self.nb_max), dtype=np.complex128)
# Note that 'ns' and 'nk' are the same for all shells
        for isp in xrange(ns):
            for ik in xrange(nk):
                nb = self.ib_win[ik, isp, 1] - self.ib_win[ik, isp, 0] + 1
# Combine all projectors of the group to one block projector
                for bl_map in block_maps:
                    p_mat[:, :] = 0.0j  # !!! Clean-up from the last k-point and block!
                    for ibl, block in enumerate(bl_map):
                        i1, i2 = block['bmat_range']
                        ish, ion = block['shell_ion']
                        nlm = i2 - i1 + 1
                        shell = self.shells[ish]
                        p_mat[i1:i2, :nb] = shell.proj_win[ion, isp, ik, :nlm, :nb]
# Now orthogonalize the obtained block projector
                    ibl_max = i2
                    p_orth, overl, eig = self.orthogonalize_projector_matrix(p_mat[:ibl_max, :nb])
# Distribute projectors back using the same mapping
                    for ibl, block in enumerate(bl_map):
                        i1, i2 = block['bmat_range']
                        ish, ion = block['shell_ion']
                        nlm = i2 - i1 + 1
                        shell = self.shells[ish]
                        shell.proj_win[ion, isp, ik, :nlm, :nb] = p_orth[i1:i2, :nb]

################################################################################
#
# gen_block_matrix_map
#
################################################################################
    def get_block_matrix_map(self):
        """
        Generates a map from a set of projectors belonging to different shells
        and ions onto a set of block projector matrices, each of which is
        orthonormalized.

        Returns the map and the maximum orbital dimension of the block projector
        matrix.


        Mapping is defined as a list of 'block_maps' corresponding to subsets
        of projectors to be orthogonalized. Each subset corresponds to a subset of sites
        and spans all orbital indices. defined by 'bl_map' as

           bl_map = [((i1_start, i1_end), (i1_shell, i1_ion)), 
                     ((i2_start, i2_end), (i2_shell, i2_ion)), 
                     ...],

        where `iX_start`, `iX_end` is the range of indices of the block matrix
        (in Python convention `iX_end = iX_last + 1`, with `iX_last` being the last index
        of the range), 
        `iX_shell` and `iX_ion` the shell and site indices. The length of the range
        should be consistent with 'nlm' dimensions of a corresponding shell, i.e.,
        `iX_end - iX_start = nlm[iX_shell]`.

        Consider particular cases:
          1. Orthogonality is ensured on each site (NORMION = True).
             For each site 'ion' we have the following mapping:

                 block_maps = [bl_map[ion] for ion in xrange(shell.nion) 
                                           for shell in shells]

                 bl_map = [((i1_start, i1_end), (i1_shell, ion)),
                           ((i2_start, i2_end), (i2_shell, ion)),
                           ...],

          2. Orthogonality is ensured on all sites within the group (NORMION = False).
             The mapping:

                 block_maps = [bl_map]

                 bl_map = [((i1_start, i1_end), (i1_shell, i1_shell.ion1)),
                           ((i1_start, i1_end), (i1_shell, i1_shell.ion2)),
                           ...
                           ((i2_start, i2_end), (i2_shell, i2_shell.ion1)),
                           ((i2_start, i2_end), (i2_shell, i2_shell.ion2)),
                           ...],
        """
        if self.normion:
# Projectors for each site are mapped onto a separate block matrix
            block_maps = []
            ndim = 0
            for ish in self.ishells:
                _shell = self.shells[ish]
                nion, ns, nk, nlm, nb_max = _shell.proj_win.shape
                ndim = max(ndim, nlm)
                for ion in xrange(nion):
                    i1_bl = 0
                    i2_bl = nlm
                    block = {'bmat_range': (i1_bl, i2_bl)}
                    block['shell_ion'] = (ish, ion)
                    bl_map = [block]
                    block_maps.append(bl_map)

        else:
# All projectors within a group are combined into one big block matrix
            block_maps = []
            bl_map = []
            i1_bl = 0
            for ish in self.ishells:
                _shell = self.shells[ish]
                nion, ns, nk, nlm, nb_max = _shell.proj_win.shape
                for ion in xrange(nion):
                    i2_bl = i1_bl + nlm
                    block = {'bmat_range': (i1_bl, i2_bl)}
                    block['shell_ion'] = (ish, ion)
                    bl_map.append(block)
                    i1_bl = i2_bl

            ndim = i2_bl
            block_maps.append(bl_map)

        return block_maps, ndim

################################################################################
#
# orthogonalize_projector_matrix()
#
################################################################################
    def orthogonalize_projector_matrix(self, p_matrix):
        """
        Orthogonalizes a projector defined by a rectangular matrix `p_matrix`.

        Parameters
        ----------

        p_matrix (numpy.array[complex]) : matrix `Nm x Nb`, where `Nm` is
          the number of orbitals, `Nb` number of bands

        Returns
        -------

        Orthogonalized projector matrix, initial overlap matrix and its eigenvalues.
        """
# TODO: check the precision of the calculations below,
#       it seems to be inferior to that of Fortran implementation
# Overlap matrix O_{m m'} = \sum_{v} P_{m v} P^{*}_{v m'}
        overlap = np.dot(p_matrix, p_matrix.conj().T)
# Calculate [O^{-1/2}]_{m m'}
        eig, eigv = np.linalg.eigh(overlap)
        assert np.all(eig > 0.0), ("Negative eigenvalues of the overlap matrix:"
           "projectors are ill-defined")
        sqrt_eig = 1.0 / np.sqrt(eig)
        shalf = np.dot(eigv * sqrt_eig, eigv.conj().T)
# Apply \tilde{P}_{m v} = \sum_{m'} [O^{-1/2}]_{m m'} P_{m' v}
        p_ortho = np.dot(shalf, p_matrix)

        return (p_ortho, overlap, eig)

################################################################################
#
# select_bands()
#
################################################################################
    def select_bands(self, eigvals):
        """
        Select a subset of bands lying within a given energy window.
        The band energies are assumed to be sorted in an ascending order.

        Parameters
        ----------
        
        eigvals (numpy.array) : all eigenvalues
        emin, emax (float) : energy window

        Returns
        -------

        ib_win, nb_min, nb_max : 
        """
# Sanity check
        if self.emin > eigvals.max() or self.emax < eigvals.min():
            raise Exception("Energy window does not overlap with the band structure")

        nk, nband, ns_band = eigvals.shape
        ib_win = np.zeros((nk, ns_band, 2), dtype=np.int32)

        ib_min = 10000000
        ib_max = 0
        for isp in xrange(ns_band):
            for ik in xrange(nk):
                for ib in xrange(nband):
                    en = eigvals[ik, ib, isp]
                    if en >= self.emin:
                        break
                ib1 = ib
                for ib in xrange(ib1, nband):
                    en = eigvals[ik, ib, isp]
                    if en > self.emax:
                        break
                else:
# If we reached the last band add 1 to get the correct bound
                    ib += 1
                ib2 = ib - 1

                assert ib1 <= ib2, "No bands inside the window for ik = %s"%(ik)

                ib_win[ik, isp, 0] = ib1
                ib_win[ik, isp, 1] = ib2

                ib_min = min(ib_min, ib1)
                ib_max = max(ib_max, ib2)

        return ib_win, ib_min, ib_max


