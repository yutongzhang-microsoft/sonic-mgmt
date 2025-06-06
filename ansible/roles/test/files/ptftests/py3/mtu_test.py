'''
Description:    This file contains the MTU test for SONIC

Usage:          Examples of how to start this script
                ptf --test-dir ptftests mtu_test.MtuTest \
                    --platform-dir ptftests \
                    --platform remote \
                    -t "router_mac='11:22:33:44:55';testbed_type='t1-64-lag'" \
                    --relax --debug info
                    --log-file /tmp/mtu_test.log  \
                    --disable-vxlan \
                    --disable-geneve
                    --disable-erspan \
                    --disable-mpls \
                    --disable-nvgre \
                    --socket-recv-size 16384
'''

# ---------------------------------------------------------------------
# Global imports
# ---------------------------------------------------------------------
import logging
import ptf
import ptf.packet as scapy

from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import test_params_get, simple_icmp_packet, simple_icmpv6_packet, send_packet,\
    simple_ip_packet, simple_tcpv6_packet, verify_packet_any_port
import macsec  # noqa F401


class MtuTest(BaseTest):
    '''
    @summary: Overview of functionality
    Test sends a jumbo ICMP echo frame with MAX MTU size and expects the reply
    back. It also sends a jumbo frame to a route destination for verifying the
    forwarding functionality

    By default.For the device configured with IP-MTU=9100, PHY-MTU=9114,
     - ICMP/IP frame, the packet-len is 9114 (This includes the 14 bytes Layer 2 Ethernet header)
    '''

    # ---------------------------------------------------------------------
    # Class variables
    # ---------------------------------------------------------------------
    ICMP_HDR_LEN = 8

    def __init__(self):
        '''
        @summary: constructor
        '''
        BaseTest.__init__(self)
        self.test_params = test_params_get()

    # ---------------------------------------------------------------------

    def setUp(self):
        self.dataplane = ptf.dataplane_instance
        self.router_mac = self.test_params['router_mac']
        self.testbed_type = self.test_params['testbed_type']
        self.testbed_mtu = self.test_params['testbed_mtu']
        self.src_host_ip = self.test_params.get('src_host_ip')
        self.src_router_ip = self.test_params.get('src_router_ip')
        self.dst_host_ip = self.test_params.get('dst_host_ip')
        self.src_host_ipv6 = self.test_params.get('src_host_ipv6')
        self.src_router_ipv6 = self.test_params.get('src_router_ipv6')
        self.dst_host_ipv6 = self.test_params.get('dst_host_ipv6')
        self.src_ptf_port_list = self.test_params.get('src_ptf_port_list')
        self.dst_ptf_port_list = self.test_params.get('dst_ptf_port_list')

    # ---------------------------------------------------------------------

    def check_icmp_mtu(self, ipv4=True):
        '''
        @summary: Check ICMP/Ping or ICMPv6/Ping6 to DUT works for MAX MTU.
        '''
        src_mac = self.dataplane.get_mac(0, self.src_ptf_port_list[0])
        pktlen = self.pktlen
        if ipv4:
            ip_src = self.src_host_ip
            ip_dst = self.src_router_ip

            pkt = simple_icmp_packet(pktlen=pktlen,
                                     eth_dst=self.router_mac,
                                     eth_src=src_mac,
                                     ip_src=ip_src,
                                     ip_dst=ip_dst,
                                     ip_ttl=64)

            exp_pkt = simple_icmp_packet(pktlen=pktlen,
                                         eth_src=self.router_mac,
                                         ip_src=ip_dst,
                                         ip_dst=ip_src,
                                         icmp_type=0)

            masked_exp_pkt = Mask(exp_pkt)
            masked_exp_pkt.set_do_not_care_scapy(scapy.Ether, "dst")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "id")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "chksum")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "ttl")
            masked_exp_pkt.set_do_not_care_scapy(scapy.ICMP, "chksum")
        else:
            ip_src = self.src_host_ipv6
            ip_dst = self.src_router_ipv6

            pkt = simple_icmpv6_packet(pktlen=pktlen,
                                       eth_dst=self.router_mac,
                                       eth_src=src_mac,
                                       ipv6_src=ip_src,
                                       ipv6_dst=ip_dst,
                                       icmp_type=128,
                                       ipv6_hlim=64)

            exp_pkt = simple_icmpv6_packet(pktlen=pktlen,
                                           eth_src=self.router_mac,
                                           ipv6_src=ip_dst,
                                           ipv6_dst=ip_src,
                                           icmp_type=129)

            masked_exp_pkt = Mask(exp_pkt)
            masked_exp_pkt.set_do_not_care_scapy(scapy.Ether, "dst")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IPv6, "hlim")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IPv6, "tc")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IPv6, "fl")

        src_port = self.src_ptf_port_list[0]
        send_packet(self, src_port, pkt)
        logging.info("Sending packet from port " +
                     str(src_port) + " to " + ip_dst)
        dst_port_list = self.src_ptf_port_list

        (matched_index, received) = verify_packet_any_port(
            self, masked_exp_pkt, dst_port_list)

        assert received

        matched_port = dst_port_list[matched_index]
        logging.info("Received packet at " + str(matched_port))

        return

    # ---------------------------------------------------------------------

    def check_ip_mtu(self, ipv4=True):
        '''
        @summary: Check unicast IP/IPv6 forwarding in DUT works for MAX MTU.
        '''
        src_mac = self.dataplane.get_mac(0, self.src_ptf_port_list[0])

        if ipv4:
            ip_src = self.src_host_ip
            ip_dst = self.dst_host_ip
            pkt = simple_ip_packet(pktlen=self.pktlen,
                                   eth_dst=self.router_mac,
                                   eth_src=src_mac,
                                   ip_src=ip_src,
                                   ip_dst=ip_dst,
                                   ip_ttl=64)

            exp_pkt = simple_ip_packet(pktlen=self.pktlen,
                                       eth_src=self.router_mac,
                                       ip_src=ip_src,
                                       ip_dst=ip_dst,
                                       ip_ttl=63)

            masked_exp_pkt = Mask(exp_pkt)
            masked_exp_pkt.set_do_not_care_scapy(scapy.Ether, "dst")
        else:
            ip_src = self.src_host_ipv6
            ip_dst = self.dst_host_ipv6
            pkt = simple_tcpv6_packet(pktlen=self.pktlen,
                                      eth_dst=self.router_mac,
                                      eth_src=src_mac,
                                      ipv6_src=ip_src,
                                      ipv6_dst=ip_dst,
                                      ipv6_hlim=64)

            exp_pkt = simple_tcpv6_packet(pktlen=self.pktlen,
                                          eth_src=self.router_mac,
                                          ipv6_src=ip_src,
                                          ipv6_dst=ip_dst,
                                          ipv6_hlim=63)

            masked_exp_pkt = Mask(exp_pkt)
            masked_exp_pkt.set_do_not_care_scapy(scapy.Ether, "dst")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IPv6, "tc")
            masked_exp_pkt.set_do_not_care_scapy(scapy.IPv6, "fl")

        src_port = self.src_ptf_port_list[0]
        send_packet(self, src_port, pkt)
        logging.info("Sending packet from port " +
                     str(src_port) + " to " + ip_dst)

        dst_port_list = self.dst_ptf_port_list
        (matched_index, received) = verify_packet_any_port(
            self, masked_exp_pkt, dst_port_list)

        assert received

        matched_port = dst_port_list[matched_index]
        logging.info("Received packet at " + str(matched_port))

        return

    # ---------------------------------------------------------------------
    def runTest(self):
        """
        @summary: Send packet(Max MTU) to test on Ping request/response and unicast IP destination.
        Expect the packet to be received from one of the expected ports
        """

        self.pktlen = self.testbed_mtu
        self.check_icmp_mtu()
        self.check_icmp_mtu(ipv4=False)
        self.check_ip_mtu()
        self.check_ip_mtu(ipv4=False)
