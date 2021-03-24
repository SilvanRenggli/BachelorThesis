/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/ipv4-global-routing-helper.h"
#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("FirstScriptExample");

int
main (int argc, char *argv[])
{
  CommandLine cmd;
  cmd.Parse (argc, argv);

  Time::SetResolution (Time::NS);
  LogComponentEnable ("UdpEchoClientApplication", LOG_LEVEL_INFO);
  LogComponentEnable ("UdpEchoServerApplication", LOG_LEVEL_INFO);

  NS_LOG_INFO ("Create nodes.");

  //Create nodes
  uint32_t NrClients = 300;
  uint32_t NrServers = 3;

  ns3::NodeContainer routers;
  routers.Create(2);
  ns3::NodeContainer clients;
  clients.Create(NrClients);
  ns3::NodeContainer servers;
  servers.Create(NrServers);
  
  //Create channels
  ns3::PointToPointHelper bottleNeckLink;
  bottleNeckLink.SetDeviceAttribute("DataRate", StringValue ("5Mbps"));
  bottleNeckLink.SetChannelAttribute ("Delay", StringValue ("2ms"));
  ns3::NetDeviceContainer routerdevices = bottleNeckLink.Install(routers);

  ns3::PointToPointHelper pointToPointLeaf; pointToPointLeaf.SetDeviceAttribute("DataRate", StringValue ("5Mbps"));
  pointToPointLeaf.SetChannelAttribute("Delay", StringValue ("2ms"));

  ns3::NetDeviceContainer leftrouterdevices;
  ns3::NetDeviceContainer clientdevices;
  ns3::NetDeviceContainer rightrouterdevices;
  ns3::NetDeviceContainer serverdevices;
  
   for (uint32_t i = 0; i < NrClients; ++i) {
        // add the client left router channels
        ns3::NetDeviceContainer cleft =
            pointToPointLeaf.Install(routers.Get(0), clients.Get(i));
        leftrouterdevices.Add(cleft.Get(0));
        clientdevices.Add(cleft.Get(1));
    }

  for (uint32_t i = 0; i < NrServers; ++i) {
        // add the servers right router channels
        ns3::NetDeviceContainer cright =
            pointToPointLeaf.Install(routers.Get(1), servers.Get(i));
        rightrouterdevices.Add(cright.Get(0));
        serverdevices.Add(cright.Get(1));
    }
   // install internet stack on all nodes
  ns3::InternetStackHelper stack;
  stack.Install(routers);
  stack.Install(clients);
  stack.Install(servers);

  //Assign ipv4Addresses
  ns3::Ipv4AddressHelper routerips =
        ns3::Ipv4AddressHelper("10.32.0.0", "255.255.255.0");
  ns3::Ipv4AddressHelper clientips =
      ns3::Ipv4AddressHelper("10.8.0.0", "255.255.255.0");
  ns3::Ipv4AddressHelper serverips =
      ns3::Ipv4AddressHelper("10.16.0.0", "255.255.255.0");

  ns3::Ipv4InterfaceContainer routerifs;
  ns3::Ipv4InterfaceContainer clientifs;
  ns3::Ipv4InterfaceContainer leftrouterifs;
  ns3::Ipv4InterfaceContainer serverifs;
  ns3::Ipv4InterfaceContainer rightrouterifs;

  // assign addresses to connection connecting routers
  routerifs = routerips.Assign(routerdevices);

  // assign addresses to connection between router and clients
    for (uint32_t i = 0; i < NrClients; ++i) {
        ns3::NetDeviceContainer ndcleft;
        ndcleft.Add(clientdevices.Get(i));
        ndcleft.Add(leftrouterdevices.Get(i));
        ns3::Ipv4InterfaceContainer ifcleft = clientips.Assign(ndcleft);
        clientifs.Add(ifcleft.Get(0));
        leftrouterifs.Add(ifcleft.Get(1));
        clientips.NewNetwork();
    }

  // assign addresses to connection between router and servers
    for (uint32_t i = 0; i < NrServers; ++i) {
        ns3::NetDeviceContainer ndcright;
        ndcright.Add(serverdevices.Get(i));
        ndcright.Add(rightrouterdevices.Get(i));
        ns3::Ipv4InterfaceContainer ifcright = serverips.Assign(ndcright);
        serverifs.Add(ifcright.Get(0));
        rightrouterifs.Add(ifcright.Get(1));
        serverips.NewNetwork();
    }
  
  ns3::Ipv4GlobalRoutingHelper::PopulateRoutingTables();

  //install applications on client and servers
  UdpEchoServerHelper echoServer (9);
  uint clientsPerServer = NrClients / NrServers;
  for (uint i = 0; i < servers.GetN (); i++)
    {
      ApplicationContainer serverApps = echoServer.Install (servers.Get (i));
      serverApps.Start (Seconds (1.0));
      serverApps.Stop (Seconds (100.0));

      UdpEchoClientHelper echoClient (serverifs.GetAddress (i), 9);
      echoClient.SetAttribute ("MaxPackets", UintegerValue (1));
      echoClient.SetAttribute ("Interval", TimeValue (Seconds (1.0)));
      echoClient.SetAttribute ("PacketSize", UintegerValue (1024));
      
      if (i < servers.GetN () - 1) {
        for (uint j = 0; j < clientsPerServer; j++)
          {
            ApplicationContainer clientApp = echoClient.Install (clients.Get(i * clientsPerServer + j));
            clientApp.Start (Seconds (2.0)); // + i * clientsPerServer + j));
            clientApp.Stop (Seconds (100.0));
          }
      } else{
        for (uint j = 0; j < NrClients - clientsPerServer * i; j++)
          {
            ApplicationContainer clientApp = echoClient.Install (clients.Get(i * clientsPerServer + j));
            clientApp.Start (Seconds (2.0)); //+ i * clientsPerServer + j));
            clientApp.Stop (Seconds (100.0));
          }
      }
    }



  Simulator::Run ();
  Simulator::Destroy ();
  return 0;
}