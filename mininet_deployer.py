#!/usr/bin/python

##############################################################################################
# Copyright (C) 2014 Pier Luigi Ventre - (Consortium GARR and University of Rome "Tor Vergata")
# Copyright (C) 2014 Giuseppe Siracusano, Stefano Salsano - (CNIT and University of Rome "Tor Vergata")
# www.garr.it - www.uniroma2.it/netgroup - www.cnit.it
#
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @author Pier Luigi Ventre <pl.ventre@gmail.com>
# @author Giuseppe Siracusano <a_siracusano@tin.it>
# @author Stefano Salsano <stefano.salsano@uniroma2.it>
#

"""Deployer implementation able to parse JSON topologies realized with TopoDesigner."""


import argparse
import sys
import os
import json

from mininet_extensions import MininetOSHI
from utility import PropertiesGenerator
from coexistence_mechanisms import *
from ingress_classifications import *

from mininet.cli import CLI
from mininet.log import lg, info, error

parser_path = "$HOME/SDN/Dreamer-Topology-Parser/"
if parser_path == "":
    print "Error : Set parser_path variable in mininet_deployer.py"
    sys.exit(-2)

if not os.path.exists(parser_path):
    error("Error : parser_path variable in mininet_deployer.py points to a non existing folder\n")
    sys.exit(-2)


sys.path.append(parser_path)
from topo_parser import TopoParser

DEFAULT_OVERALL_INFO_FILE = '/tmp/overall_info.json'
overall_info_file = DEFAULT_OVERALL_INFO_FILE

#SINGLE_CONNECTION = True
SINGLE_CONNECTION = False
""" if SINGLE_CONNECTION is True, one of the Core Router is choosen as gateway for the "management"
ssh connections from the hosting environment to the mininet VMs
if SINGLE_CONNECTION is False, each Mininet VM has an additional interface directly connected to
an interface of the hosting environment and ssh is performed "out of band"
"""

def topo(topology):
    """Builds Topology from a json file generated by Topology3D

    It also creates Configuration File for VLL pusher
    it saves a json files with all the node details (default in /tmp/overall_info.json)
    so that node.js can parse it and update the web gui
    """

    verbose = True
    if verbose:
        print "*** Build Topology From Parsed File"
        print "*** Topology file : ", topology 
        print "*** NodeInfo file: ", overall_info_file
        print "*** Topology format version: ", tf_version
    parser = TopoParser(topology, verbose = True, version=tf_version)
    ppsubnets = parser.getsubnets()
    #NB a submet could include multiple links if a legacy switch is used
    # currently only the first link is considered, therefore
    # legacy switches are not supported
    vlls = parser.getVLLs()
    pws = parser.getPWs()
    vss = parser.getVSs()
    # XXX
    if parser.generated == False:
        if verbose:
            print "*** No Autogenerated"

        generator = PropertiesGenerator(False)
        if verbose:
            print "*** Build Vertices Properties"
            cr_oshis_properties = generator.getVerticesProperties(parser.cr_oshis)
            for parser_cr_property, cr_property in zip(parser.cr_oshis_properties, cr_oshis_properties):
                parser_cr_property['loopback'] = cr_property.loopback

            pe_oshis_properties = generator.getVerticesProperties(parser.pe_oshis)
            for parser_pe_property, pe_property in zip(parser.pe_oshis_properties, pe_oshis_properties):
                parser_pe_property['loopback'] = pe_property.loopback
            #cers_properties = generator.getVerticesProperties(parser.cers)

        if verbose:
            print "*** Build Point-To-Point Links Properties"
        pp_properties = []
        for ppsubnet in ppsubnets:
            pp_properties.append(generator.getLinksProperties(ppsubnet.links))
        
        if verbose:
            print "*** Build VLLs Properties"
        vlls_properties = []
        for vll in vlls:
            vlls_properties.append(generator.getVLLProperties(vll))

        if verbose:
            print "*** Build PWs Properties"
        pws_properties = []
        for pw in pws:
            pws_properties.append(generator.getVLLProperties(pw))

        if verbose:
            print "*** Build VSs Properties"
        vss_properties = []
        for vs in vss:
            vs_properties = generator.getVSProperties(vs)
            vss_properties.append(vs_properties)           

    set_cr_oshis = parser.cr_oshis
    set_pe_oshis = parser.pe_oshis
    set_cers = parser.cers
    set_ctrls = parser.ctrls

    set_all_nodes = []
    set_all_nodes.extend(set_cr_oshis)
    set_all_nodes.extend(set_pe_oshis)
    set_all_nodes.extend(set_cers)
    set_all_nodes.extend(set_ctrls)

    net = MininetOSHI(verbose)

    if verbose:
        print "*** Build OSHI CRs"
    i = 0   
    for croshi in set_cr_oshis:
        net.addCrOSHI(parser.cr_oshis_properties[i], croshi)
        if verbose:
            print "*** %s - %s" %(croshi, parser.cr_oshis_properties[i])
        i = i + 1

    if verbose:
        print "*** Build OSHI PEs" 
    i = 0
    for peoshi in set_pe_oshis:
        net.addPeOSHI(parser.pe_oshis_properties[i], peoshi)
        if verbose:
            print "*** %s - %s" %(peoshi, parser.pe_oshis_properties[i])    
        i = i + 1

    net.addCoexistenceMechanism("COEXH", 0)

    if verbose:
        print "*** Build CONTROLLERS"
    i = 0
    for ctrl in set_ctrls:
        net.addController(parser.ctrls_properties[i], ctrl)
        if verbose:
            print "*** %s - %s" %(ctrl, parser.ctrls_properties[i]) 
        i = i + 1

    if verbose:
        print "*** Build CERS"
    i = 0
    for cer in set_cers:
        net.addCeRouter(0, parser.cers_properties[i],  name = cer)
        if verbose:
            print "*** %s - %s" %(cer, parser.cers_properties[i])
        i = i + 1

    if verbose:
        print "*** Build node for management network"
    mgmt = net.addManagement(name="mgm1")

    if SINGLE_CONNECTION:
        croshi = net.getNodeByName(croshi)  
        
        linkproperties = generator.getLinksProperties([(croshi.name, mgmt.name)])
        net.addLink(croshi, mgmt, linkproperties[0])
        if verbose:         
            print "*** MANAGEMENT CONNECTION: ", mgmt.name, "To", croshi.name, "-", linkproperties[0]
    else:
        i = 0   
        for a_node in set_all_nodes:
            a_node = net.getNodeByName(a_node)  
            linkproperties = generator.getLinksProperties([(a_node.name, mgmt.name)])
            net.addLink(a_node, mgmt, linkproperties[0])
            if verbose:         
                print "*** MANAGEMENT CONNECTION: ", a_node.name, "To", mgmt.name, "-", linkproperties[0]
            i = i + 1


    if verbose: 
        print "*** Create Point To Point Networks"
    i = 0
    for ppsubnet in ppsubnets:
            links = ppsubnet.links
            #if a ppsubnet has more than one link, only the first one is considered
            if verbose:
                print "*** Subnet: Node %s - Links %s" %(ppsubnet.nodes, links)
            node1 = net.getNodeByName(links[0][0])
            node2 = net.getNodeByName(links[0][1])
            net.addLink(node1, node2, pp_properties[i][0])
            if verbose:         
                #print "*** Connect", node1, "To", node2
                print "*** Link Properties", pp_properties[i][0]
            i = i + 1

    i = 0
    for vll in vlls:
        node1 = net.getNodeByName(vll[0])
        node2 = net.getNodeByName(vll[1])
        net.addVLL(node1, node2, vlls_properties[i])
        if verbose:         
            print "*** VLLs Properties", vlls_properties[i]
        i = i + 1   

    i = 0
    for pw in pws:
        node1 = net.getNodeByName(pw[0])
        node2 = net.getNodeByName(pw[1])
        net.addPW(node1, node2, pws_properties[i])
        if verbose:         
            print "*** PWs Properties", pws_properties[i]
        i = i + 1

    i = 0
    for vs in vss:
        endnodes = []
        for node in vs:
            endnodes.append(net.getNodeByName(node))
        net.addVS(endnodes, vss_properties[i])
        if verbose:         
            print "*** VSs Properties", vss_properties[i]
        i = i + 1
    
    my_info = net.start()
    store_overall_info(my_info)
    if not no_cli:
        CLI(net)
        net.stop()

def store_overall_info(my_info):

    stro = json.dumps(my_info)
    if os.path.exists(overall_info_file):
        os.remove(overall_info_file)
    overall_file = open(overall_info_file,'a+')
    overall_file.write(stro+"\n")
    overall_file.close()

def clean_all():
    net = MininetOSHI(True)
    net.stop()

def parse_cmd_line():
    parser = argparse.ArgumentParser(description='Mininet Extensions')
    parser.add_argument('--topology', dest='topoInfo', action='store', default='topo/version2.json', help='topo:param see README for further details')
    parser.add_argument('--nodeinfo', dest='nodeInfo', action='store', default= DEFAULT_OVERALL_INFO_FILE, help='file that stores the node info to be processed by node.js')
    parser.add_argument('--version', dest='version', action='store', default=1, help='topology format version')
    parser.add_argument('--stop-all', dest='clean_all',action='store_true', help='Clean all mininet environment')
    parser.add_argument('--no-cli', dest='no_cli',action='store_true', help='Do not show Mininet CLI')

    args = parser.parse_args()
    
    if args.clean_all:
        clean_all()
        sys.exit(1)

    if len(sys.argv)==1 and args.clean_all == False:
            parser.print_help()
            sys.exit(1)
    topo_data = args.topoInfo  

    global overall_info_file
    global tf_version 
    global no_cli
    tf_version = args.version
    overall_info_file =  args.nodeInfo
    no_cli = args.no_cli
    return (topo_data)

if __name__ == '__main__':
    (topology) = parse_cmd_line()
    topo(topology)
