# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
""" Unit tests for cube extraction utilities """

import unittest
import os
import numpy as np
from tempfile import mkdtemp
from subprocess import call

import iris
from iris.tests import IrisTest
from iris.coords import DimCoord
from iris.exceptions import CoordinateNotFoundError

from improver.utilities.cube_extraction import (parse_constraint_list,
                                                extract_subcube)


def set_up_precip_probability_cube():
    """
    Set up a cube with spatial probabilities of precipitation at three
    exceedance thresholds
    """
    data = np.array([[[0.85, 0.95, 0.73],
                      [0.75, 0.85, 0.65],
                      [0.70, 0.80, 0.62]],
                     [[0.18, 0.20, 0.15],
                      [0.11, 0.16, 0.09],
                      [0.10, 0.14, 0.03]],
                     [[0.03, 0.04, 0.01],
                      [0.02, 0.02, 0.00],
                      [0.01, 0.00, 0.00]]])

    mmh_to_ms = 0.001/3600.
    threshold = DimCoord(mmh_to_ms*np.array([0.03, 0.1, 1.0]),
                         long_name="threshold", units="m s-1")
    ycoord = DimCoord(np.arange(3), "projection_y_coordinate")
    xcoord = DimCoord(np.arange(3), "projection_x_coordinate")

    cube = iris.cube.Cube(data, long_name="probability_of_precipitation",
                          dim_coords_and_dims=[(threshold, 0), (ycoord, 1),
                                               (xcoord, 2)], units="1")
    return cube


class Test_parse_constraint_list(IrisTest):

    """ Test function to parse constraints and units into dictionaries """

    def setUp(self):
        """ Set up some constraints to parse """
        self.constraints = ["percentile=10", "threshold=0.1"]

    def test_basic_no_units(self):
        """ Test simple key-value splitting with no units """
        cdict, udict = parse_constraint_list(self.constraints, None)
        self.assertEqual(cdict["percentile"], 10)
        self.assertEqual(cdict["threshold"], 0.1)
        self.assertFalse(udict)

    def test_some_units(self):
        """ Test units list containing "None" elements is correctly parsed """
        units = ["None", "mm h-1"]
        _, udict = parse_constraint_list(self.constraints, units)
        self.assertEqual(udict["threshold"], "mm h-1")
        self.assertNotIn("percentile", udict.keys())

    def test_unmatched_units(self):
        """ Test for ValueError if units list does not match constraints """
        units = ["mm h-1"]
        msg = "units list must match constraints"
        with self.assertRaisesRegexp(ValueError, msg):
            parse_constraint_list(self.constraints, units)


class Test_extract_subcube(IrisTest):

    """ Test function to extract subcube according to constraints """

    def setUp(self):
        """ Save temporary input cube to file """
        self.precip_cube = set_up_precip_probability_cube()
        self.directory = mkdtemp()
        self.filepath = os.path.join(self.directory, 'tmp_precip_cube.nc')
        iris.save(self.precip_cube, self.filepath)

    def tearDown(self):
        """ Remove temporary path created for testing """
        call(['rm', '-f', self.filepath])
        call(['rmdir', self.directory])

    def test_basic_no_units(self):
        """ Test cube extraction for single constraint without units """
        constraint_dict = {"name": "probability_of_precipitation"}
        cube = extract_subcube(self.filepath, constraint_dict, None)
        self.assertIsInstance(cube, iris.cube.Cube)
        reference_data = self.precip_cube.data
        self.assertArrayEqual(cube.data, reference_data)

    def test_basic_with_units(self):
        """ Test cube extraction for single constraint with units """
        constraint_dict = {"threshold": 0.1}
        units_dict = {"threshold": "mm h-1"}
        cube = extract_subcube(self.filepath, constraint_dict, units_dict)
        self.assertIsInstance(cube, iris.cube.Cube)
        self.assertEqual(cube.coord("threshold").units, "mm h-1")
        reference_data = self.precip_cube.data[1, :, :]
        self.assertArrayEqual(cube.data, reference_data)

    def test_raises_mismatch_error(self):
        """ Test error is raised if the output cube is empty """
        constraint_dict = {"threshold": 6}
        with self.assertRaises(ValueError):
            extract_subcube(self.filepath, constraint_dict, None)

    def test_multiple_constraints_with_units(self):
        """ Test behaviour with a list of constraints and units """
        constraint_dict = {"name": "probability_of_precipitation",
                           "threshold": 0.03}
        units_dict = {"threshold": "mm h-1"}
        cube = extract_subcube(self.filepath, constraint_dict, units_dict)
        self.assertIsInstance(cube, iris.cube.Cube)
        reference_data = self.precip_cube.data[0, :, :]
        self.assertArrayEqual(cube.data, reference_data)

    def test_error_non_coord_units(self):
        """ Test error raised if units are provided for a non-coordinate
        constraint """
        constraint_dict = {"name": "probability_of_precipitation"}
        units_dict = {"name": "1"}
        with self.assertRaises(CoordinateNotFoundError):
            extract_subcube(self.filepath, constraint_dict, units_dict)


if __name__ == '__main__':
    unittest.main()
