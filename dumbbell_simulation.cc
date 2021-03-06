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

#include "ns3/point-to-point-helper.h"
#include <fstream>
#include "ns3/core-module.h"
#include "ns3/applications-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"
#include "ns3/mobility-module.h"
#include <ns3/buildings-module.h>
#include "ns3/building-position-allocator.h"
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <sstream>
#include "ns3/flow-monitor-module.h"
#include "ns3/tcp-stream-helper.h"
#include "ns3/tcp-stream-interface.h"
#include "ns3/dash-application-installer.h"
#include "ns3/dash-event-scheduler.h"

template <typename T>
std::string ToString(T val)
{
    std::stringstream stream;
    stream << val;
    return stream.str();
}

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("TcpStreamExample");

// The simulation id is used to distinguish log file results from potentially multiple consequent simulation runs.
uint32_t simulationId;
uint32_t numberOfClients;
uint32_t numberOfServers;
uint32_t liveInputs;
uint32_t enablePacing;
uint32_t live_event_index;
std::string simulationName;
std::string tcpModel;
std::string bottleNeckRate;
std::string bottleNeckDelay;
std::string channelRate;
std::string channelDelay;

std::ofstream dataLog;
std::ofstream eventLog; 


int
main (int argc, char *argv[])
{

  LogComponentEnable ("TcpStreamExample", LOG_LEVEL_INFO);
  LogComponentEnable ("TcpStreamClientApplication", LOG_LEVEL_INFO);
  LogComponentEnable ("TcpStreamServerApplication", LOG_LEVEL_INFO);


  CommandLine cmd;
  cmd.Usage ("Simulation of streaming with DASH.\n");
  cmd.AddValue ("simulationName", "The simulation's name (for logging purposes)", simulationName);
  cmd.AddValue ("simulationId", "The simulation's index (for logging purposes)", simulationId);
  cmd.AddValue ("numberOfClients", "The number of clients", numberOfClients);
  cmd.AddValue ("numberOfServers", "The number of servers", numberOfServers);
  cmd.AddValue ("tcp", "The tcp implementation that the simulation uses", tcpModel);
  cmd.AddValue ("bottleNeckRate", "The data rate of the bottleneck link", bottleNeckRate);
  cmd.AddValue ("bottleNeckDelay", "The delay of the bottleneck link", bottleNeckDelay);
  cmd.AddValue ("channelRate", "The data rate of all other links", channelRate);
  cmd.AddValue ("channelDelay", "The delay of all other links", channelDelay);
  cmd.AddValue ("liveInputs", "Wheter live inputs are enabled or not. 1 or 0", liveInputs);
  cmd.AddValue ("packetPacing", "Wheter packet pacing is enabled or not. 1 or 0", enablePacing);
  cmd.Parse (argc, argv);

  live_event_index = 0;
  DataRate maxPacingRate (channelRate);

  TypeId tcpTid;
  NS_ABORT_MSG_UNLESS (TypeId::LookupByNameFailSafe (tcpModel, &tcpTid), "TypeId " << tcpModel << " not found");
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", TypeIdValue (TypeId::LookupByName (tcpModel)));
  Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue (1446));
  Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue (524288));
  Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue (524288));

  


  //Create nodes

  ns3::NodeContainer routerNodes;
  routerNodes.Create(2);
  ns3::NodeContainer clientNodes;
  clientNodes.Create(numberOfClients);
  ns3::NodeContainer serverNodes;
  serverNodes.Create(numberOfServers);
  
  //Create channels

  ns3::PointToPointHelper bottleNeckLink;
  bottleNeckLink.SetDeviceAttribute("DataRate", StringValue (bottleNeckRate)); 
  bottleNeckLink.SetChannelAttribute ("Delay", StringValue (bottleNeckDelay));
  ns3::NetDeviceContainer routerdevices = bottleNeckLink.Install(routerNodes);

  ns3::NetDeviceContainer rightrouterdevices;
  ns3::NetDeviceContainer serverdevices;
  
  Config::SetDefault ("ns3::TcpSocketState::EnablePacing", BooleanValue (enablePacing));
  Config::SetDefault ("ns3::TcpSocketState::MaxPacingRate", DataRateValue (maxPacingRate));

  for (uint32_t i = 0; i < numberOfServers; ++i) {
        // add the servers right router channels
        ns3::NetDeviceContainer serverClient =
            bottleNeckLink.Install(routerNodes.Get(1), serverNodes.Get(i));
        rightrouterdevices.Add(serverClient.Get(0));
        serverdevices.Add(serverClient.Get(1));
    }

  
  ns3::PointToPointHelper pointToPointLeaf; 
  pointToPointLeaf.SetDeviceAttribute("DataRate", StringValue (channelRate)); 
  pointToPointLeaf.SetChannelAttribute("Delay", StringValue (channelDelay));

  ns3::NetDeviceContainer leftrouterdevices;
  ns3::NetDeviceContainer clientdevices;
  
   for (uint32_t i = 0; i < numberOfClients; ++i) {
        // add the client left router channels
        ns3::NetDeviceContainer routerClient =
            pointToPointLeaf.Install(routerNodes.Get(0), clientNodes.Get(i));
        leftrouterdevices.Add(routerClient.Get(0));
        clientdevices.Add(routerClient.Get(1));
    }

  
  // install internet stack on all nodes

  ns3::InternetStackHelper stack;

  Config::SetDefault ("ns3::TcpSocketState::EnablePacing", BooleanValue (false));
  stack.Install(routerNodes);

  Config::SetDefault ("ns3::TcpSocketState::EnablePacing", BooleanValue (enablePacing));
  stack.Install(clientNodes);
  stack.Install(serverNodes);

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
    for (uint32_t i = 0; i < numberOfClients; ++i) {
        ns3::NetDeviceContainer ndcleft;
        ndcleft.Add(clientdevices.Get(i));
        ndcleft.Add(leftrouterdevices.Get(i));
        ns3::Ipv4InterfaceContainer ifcleft = clientips.Assign(ndcleft);
        clientifs.Add(ifcleft.Get(0));
        leftrouterifs.Add(ifcleft.Get(1));
        clientips.NewNetwork();
    }

  // assign addresses to connection between router and servers
    for (uint32_t i = 0; i < numberOfServers; ++i) {
        ns3::NetDeviceContainer ndcright;
        ndcright.Add(serverdevices.Get(i));
        ndcright.Add(rightrouterdevices.Get(i));
        ns3::Ipv4InterfaceContainer ifcright = serverips.Assign(ndcright);
        serverifs.Add(ifcright.Get(0));
        rightrouterifs.Add(ifcright.Get(1));
        serverips.NewNetwork();
    }

 /* Populate routing table */
  Ipv4GlobalRoutingHelper::PopulateRoutingTables ();
  uint16_t port = 9;

  // create folder for logged data
  const char * mylogsDir = dashLogDirectory.c_str();
  mkdir (mylogsDir, 0775);
  std::string algodirstr (dashLogDirectory +  simulationName );  
  const char * algodir = algodirstr.c_str();
  mkdir (algodir, 0775);
  std::string dirstr (dashLogDirectory + simulationName + "/" + ToString (numberOfClients) + "/");
  const char * dir = dirstr.c_str();
  mkdir(dir, 0775);

  
 // create logfile for event logging
  std::string Log = dashLogDirectory + simulationName + "/" + ToString(numberOfClients)  + "/sim" + ToString(simulationId) + "_" + "event_log.txt";
  std::string liveEventFilePath = dirstr + "sim" + ToString(simulationId) + "_real_time_events.txt";
  // load scheduled events
  DashEventScheduler scheduler (Log, liveEventFilePath, liveInputs);
  scheduler.ScheduleEvents((dirstr + "sim" + ToString(simulationId) + "_event_schedule.txt").c_str());

  

  // eventLog.open (Log.c_str ());
  // eventLog << "Time_Now;Event;Value\n";
  // eventLog.flush ();
  
  DashApplicationInstaller installer ((dirstr + "sim" + ToString(simulationId) + "_clients.txt"), port, simulationId, simulationName);
  installer.InstallClients (clientNodes, serverNodes, serverifs);
  installer.InstallServers (serverNodes);
 
  scheduler.LogEvent ("BottleneckRate", std::stoi(bottleNeckRate));
  NS_LOG_INFO ("Run Simulation.");
  NS_LOG_INFO ("Sim: " << simulationId << "Clients: " << numberOfClients);
  Simulator::Run ();
  Simulator::Destroy ();
  dataLog.close();
  scheduler.CleanUp();
  NS_LOG_INFO ("Done.");
  return 0;
}