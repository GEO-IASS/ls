#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    GNU Gama interface classes for Land Surveying Plug-in for QGIS
    GPL v2.0 license
    Copyright (C) 2014-  DgiKom Kft. http://digikom.hu
    .. moduleauthor::Zoltan Siki <siki@agt.bme.hu>
"""

import re
import os
from xml.dom import minidom, Node
from subprocess import call
import tempfile
# surveying calculation modules
from base_classes import *
from surveying_util import *
# debugging
from PyQt4.QtCore import pyqtRemoveInputHook
import pdb

class GamaInterface(object):
    """
        interface class to GNU Gama
    """
    def __init__(self, dimension=2, probability=0.95, stdev_angle=3, stdev_dist=3, stdev_dist1=3):
        self.dimension = dimension
        self.probability = probability
        self.stdev_angle = stdev_angle
        self.stdev_dist = stdev_dist
        self.stdev_dist1 = stdev_dist1
        self.points = []
        self.observations = []
        # get operating system dependent file name of gama_local
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        gama_prog = os.path.join(plugin_dir, 'gama-local')
        if not os.path.exists(gama_prog):
            gama_prog += '.exe'
            if not os.path.exists(gama_prog):
                gama_prog = None
        self.gama_prog = gama_prog

    def add_point(self, point, state='ADJ'):
        """
            Add point to adjustment
            :param point Point
            :state FIX or ADJ
        """
        for p, s in self.points:
            # avoid duplicated points
            if p.id == point.id:
                return
        self.points.append([point, state])

    def add_observation(self, obs):
        """
            Add observation to adjustment
            :param obs PolarObservation
        """
        self.observations.append(obs)

    def remove_last_observation(self, st=False):
        """
            remove last observation or station data
            :param st: False - remove single observation, True remove station
        """
        if len(self.observations):
            if st:
                o = self.observations.pop()
                while len(self.observations) and o.station is None:
                    o = self.observations.pop()
            else:
                self.observations.pop()

    def adjust(self):
        """
            Export data to GNU Gama xml, adjust the network and read result
            :return None/0 failure/success
        """
        # fix = 0 free network
        fix = 0
        adj = 0
        for p, s in self.points:
            if s == 'FIX':
                fix += 1
            else:
                adj += 1
        if adj == 0 or len(self.observations) == 0:
            # no unknowns or observations
            return None
        doc = minidom.Document()
        doc.appendChild(doc.createComment('Gama XML created by Land Surveying plugin for QGIS'))
        gama_local = doc.createElement('gama-local')
        gama_local.setAttribute('version', '2.0')
        doc.appendChild(gama_local)
        network = doc.createElement('network')
        network.setAttribute('axes-xy', 'ne')
        network.setAttribute('angles', 'left-handed')
        gama_local.appendChild(network)
        description = doc.createElement('description')
        if self.dimension == 1:
            description.appendChild(doc.createTextNode('GNU Gama 1D network'))
        elif self.dimension == 2:
            description.appendChild(doc.createTextNode('GNU Gama 2D network'))
        elif self.dimension == 3:
            description.appendChild(doc.createTextNode('GNU Gama 3D network'))
        network.appendChild(description)
        parameters = doc.createElement('parameters')
        parameters.setAttribute('sigma-apr', '1')
        parameters.setAttribute('conf-pr', str(self.probability))
        parameters.setAttribute('tol-abs', '1000')
        parameters.setAttribute('sigma-act', 'aposteriori')
        parameters.setAttribute('update-constrained-coordinates', 'yes')
        network.appendChild(parameters)
        points_observations = doc.createElement('points-observations')
        points_observations.setAttribute('distance-stdev', str(self.stdev_dist) + ' ' + str(self.stdev_dist1)) 
        points_observations.setAttribute('direction-stdev', str(self.stdev_angle))
        points_observations.setAttribute('angle-stdev', str(math.sqrt(self.stdev_angle * 2)))
        points_observations.setAttribute('zenith-angle-stdev', str(self.stdev_angle))
        network.appendChild(points_observations)
        for p, s in self.points:
            if self.dimension == 1:
                tmp = doc.createElement('point')
                tmp.setAttribute('id', p.id)
                if p.z is not None:
                    tmp.setAttribute('z', str(p.z))
                if s == 'FIX':
                    tmp.setAttribute('fix', 'z')
                else:
                    if fix == 0:
                        tmp.setAttribute('adj', 'Z')
                    else:
                        tmp.setAttribute('adj', 'z')
                points_observations.appendChild(tmp)
            elif self.dimension == 2:
                tmp = doc.createElement('point')
                tmp.setAttribute('id', p.id)
                if p.e is not None and p.n is not None:
                    tmp.setAttribute('y', str(p.e))
                    tmp.setAttribute('x', str(p.n))
                if s == 'FIX':
                    tmp.setAttribute('fix', 'xy')
                else:
                    if fix == 0:
                        # free network
                        tmp.setAttribute('adj', 'XY')
                    else:
                        tmp.setAttribute('adj', 'xy')
                points_observations.appendChild(tmp)
            elif self.dimension == 3:
                tmp = doc.createElement('point')
                tmp.setAttribute('id', p.id)
                if p.e is not None and p.n is not None:
                    tmp.setAttribute('y', str(p.e))
                    tmp.setAttribute('x', str(p.n))
                if p.z is not None:
                    tmp.setAttribute('z', str(p.z))
                if s == 'FIX':
                    tmp.setAttribute('fix', 'xyz')
                else:
                    if fix == 0:
                        tmp.setAttribute('adj', 'XYZ')
                    else:
                        tmp.setAttribute('adj', 'xyz')
                points_observations.appendChild(tmp)
        for o in self.observations:
            if o.station == 'station':
                # station record
                sta = doc.createElement('obs')
                sta.setAttribute('from', o.point_id)
                ih = o.th
                points_observations.appendChild(sta)
            else:
                # observation
                if self.dimension == 2:
                    # horizontal network
                    if o.hz is not None:
                        tmp = doc.createElement('direction')
                        tmp.setAttribute('to', o.point_id)
                        tmp.setAttribute('val', str(o.hz.get_angle('GON')))
                        sta.appendChild(tmp)
                    if o.d is not None:
                        # horizontal distance
                        hd = o.horiz_dist()
                        if hd is not None:
                            tmp = doc.createElement('distance')
                            tmp.setAttribute('to', o.point_id)
                            tmp.setAttribute('val', str(hd))
                            sta.appendChild(tmp)
                elif self.dimension == 1:
                    # elevations only
                    pass
                elif self.dimension == 3:
                    # 3d
                    pass
                else:
                    # unknown dimension
                    return None
        #print doc.toprettyxml(indent="  ")
        # generate temp file name
        f =  tempfile.NamedTemporaryFile('w')
        tmp_name = f.name
        f.close()
        doc.writexml(open(tmp_name + '.xml', 'w'))
        doc.unlink()
        # run gama-local
        if self.gama_prog is None:
            return None
        status = call([self.gama_prog, tmp_name + '.xml', '--text',
            tmp_name + '.txt', '--xml', tmp_name + 'out.xml'])
        if status != 0:
            # error running GNU gama TODO
            return None
        doc = minidom.parse(tmp_name + 'out.xml')
        f_txt = open(tmp_name + '.txt', 'r')
        res = f_txt.read()
        f.close()
        # store coordinates
        adj_nodes = doc.getElementsByTagName('adjusted')
        if len(adj_nodes) < 1:
            return res
        adj_node = adj_nodes[0]
        for pp in adj_node.childNodes:
            if pp.nodeName == 'point':
                for ppp in pp.childNodes:
                    if ppp.nodeName == 'id':
                        p = Point(ppp.firstChild.data)
                    elif ppp.nodeName == 'Y' or ppp.nodeName == 'y':
                        p.e = float(ppp.firstChild.data)
                    elif ppp.nodeName == 'X' or ppp.nodeName == 'x':
                        p.n = float(ppp.firstChild.data)
                    elif ppp.nodeName == 'Z' or ppp.nodeName == 'z':
                        p.z = float(ppp.firstChild.data)
                ScPoint(p).store_coord(self.dimension)
        # get orientations TODO
        #oris = doc.getElementsByTagName('orientation')
        #for ori in oris:
        #    pass
        # remove input xml and output xml
        try:
            #os.remove(tmp_name + '.txt') # TODO remove comment after testing
            #os.remove(tmp_name + '.xml')
            os.remove(tmp_name + 'out.xml')
        except OSError:
            pass
        return res

if __name__ == "__main__":
    """
        unit test
    """
    gi = GamaInterface()
    gi.add_point(Point('1', 0, 0))
    gi.add_point(Point('2', 211.70, 0))
    gi.add_point(Point('3', 257.95, 375.64))
    gi.add_point(Point('4', 78.1562, 395.49))
    gi.add_point(Point('5', -60.35, 387.99))
    gi.add_observation(PolarObservation('1', 'station'))
    gi.add_observation(PolarObservation('2', None, Angle('42-56-02', 'DMS'),
        Angle('87-35-39', 'DMS'), Distance(211.886, 'SD')))
    gi.add_observation(PolarObservation('3', None, Angle('347-24-35', 'DMS'),
        Angle('88-54-24', 'DMS'), Distance(455.774, 'SD')))
    gi.add_observation(PolarObservation('4', None, Angle('324-06-32', 'DMS'),
        Angle('90-00-36', 'DMS'), Distance(403.150, 'SD')))
    gi.add_observation(PolarObservation('5', None, Angle('304-05-19', 'DMS'),
        Angle('89-58-23', 'DMS'), Distance(392.665, 'SD')))
    gi.add_observation(PolarObservation('2', 'station'))
    gi.add_observation(PolarObservation('1', None, Angle('304-20-43', 'DMS'),
        Angle('92-27-19', 'DMS'), Distance(211.894, 'SD')))
    gi.add_observation(PolarObservation('5', None, Angle('359-18-19', 'DMS'),
        Angle('91-03-52', 'DMS'), Distance(473.977, 'SD')))
    gi.add_observation(PolarObservation('4', None, Angle('15-41-16', 'DMS'),
        Angle('91-14-36', 'DMS'), Distance(417.565, 'SD')))
    gi.add_observation(PolarObservation('3', None, Angle('41-22-11', 'DMS'),
        Angle('90-02-29', 'DMS'), Distance(378.506, 'SD')))
    gi.add_observation(PolarObservation('5', 'station'))
    gi.add_observation(PolarObservation('4', None, Angle('324-16-52', 'DMS'),
        Angle('90-06-46', 'DMS'), Distance(138.703, 'SD')))
    gi.add_observation(PolarObservation('3', None, Angle('329-36-15', 'DMS'),
        Angle('88-27-29', 'DMS'), Distance(318.672, 'SD')))
    gi.add_observation(PolarObservation('2', None, Angle('22-20-43', 'DMS'),
        Angle('88-55-56', 'DMS'), Distance(473.959, 'SD')))
    gi.add_observation(PolarObservation('1', None, Angle('48-32-26', 'DMS'),
        Angle('90-01-16', 'DMS'), Distance(392.662, 'SD')))
    gi.add_observation(PolarObservation('4', 'station'))
    gi.add_observation(PolarObservation('2', None, Angle('346-38-25', 'DMS'),
        Angle('88-45-44', 'DMS'), Distance(417.543, 'SD')))
    gi.add_observation(PolarObservation('1', None, Angle('16-28-34', 'DMS'),
        Angle('89-59-40', 'DMS'), Distance(403.146, 'SD')))
    gi.add_observation(PolarObservation('5', None, Angle('92-11-53', 'DMS'),
        Angle('89-57-38', 'DMS'), Distance(138.704, 'SD')))
    gi.add_observation(PolarObservation('3', 'station'))
    gi.add_observation(PolarObservation('5', None, Angle('59-45-52', 'DMS'),
        Angle('91-33-41', 'DMS'), Distance(318.673, 'SD')))
    gi.add_observation(PolarObservation('1', None, Angle('2-01-09', 'DMS'),
        Angle('91-05-51', 'DMS'), Distance(455.772, 'SD')))
    gi.add_observation(PolarObservation('2', None, Angle('334-33-23', 'DMS'),
        Angle('89-57-40', 'DMS'), Distance(378.487, 'SD')))
    gi.adjust()
