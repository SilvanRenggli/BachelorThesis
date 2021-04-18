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

template <typename T>
std::string ToString(T val)
{
    std::stringstream stream;
    stream << val;
    return stream.str();
}

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("TcpStreamExample");

uint64_t segmentDuration;
// The simulation id is used to distinguish log file results from potentially multiple consequent simulation runs.
uint32_t simulationId;
uint32_t numberOfClients;
uint32_t numberOfServers;
uint32_t pandaClients;
uint32_t tobascoClients;
uint32_t festiveClients;
uint32_t liveInputs;
uint32_t enablePacing;
uint32_t live_event_index;
std::string simulationName;
std::string segmentSizeFilePath;
std::string tcpModel;
std::string bottleNeckRate;
std::string bottleNeckDelay;
std::string channelRate;
std::string channelDelay;

std::ofstream dataLog;
std::ofstream eventLog; 

std::string
GetAdaptionAlgo (uint16_t client_id){
  if (client_id < pandaClients){
    return "panda";
  }else if (client_id < pandaClients + tobascoClients){
    return "tobasco";
  }else{
    return "festive";
  }
}

void
LogPacket (Ptr<const Packet> p)
{
  dataLog << Simulator::Now ().GetMicroSeconds () / (double) 1000000 << ";" << p->GetSize () << ";\n";
  dataLog.flush ();
}

void
LogEvent (const char *event ,uint64_t value)
{
  eventLog << Simulator::Now ().GetMicroSeconds () / (double) 1000000 << ";" << event << ";" << value << "\n";
  eventLog.flush ();
}

void
changeBottleneckRate (const std::string& value)
{
  Config::Set("/NodeList/0/DeviceList/0/$ns3::PointToPointNetDevice/DataRate", StringValue(value) );
  Config::Set("/NodeList/1/DeviceList/0/$ns3::PointToPointNetDevice/DataRate", StringValue(value) );
  LogEvent ("BottleneckRate", std::stoi(value));
}

void
ScheduleEvents (const char* eventFilePath)
{
  //std::cerr << "called " << eventFilePath <<"\n";
  std::ifstream efile(eventFilePath);
  std::string line;
  std::getline(efile, line);
  while (std::getline(efile, line))
  {
    std::istringstream iss(line);
    std::string event;
    int time;
    std::string value;
    if (!(iss >> event >> time >> value)) {
      std::cerr << "invalid event schedule file!" << "\n";
    }
    if (event == "BottleNeckRate"){
      //Simulator::Schedule(Seconds(time), &changeBottleneckRate, (value + "Mbps").c_str());
      Simulator::Schedule(Seconds(time), &changeBottleneckRate, value);
    }
    std::cerr << event << " " << std::to_string(time) << " " << value << "\n";
  }
  efile.close();
}

void
CheckLiveEvents (const std::string& liveEventFilePath)
{
  std::cerr << "called " << liveEventFilePath <<"\n";
  std::ifstream efile(liveEventFilePath);
  std::string line;
  uint64_t line_count = 0;
  while (std::getline(efile, line))
  { 
    line_count ++;
    if(line_count > live_event_index){
      std::istringstream iss(line);
      std::cerr << line <<"\n";
      std::string event;
      std::string value;
      if (!(iss >> event >> value)) {
        //std::cerr << "invalid event schedule file!" << "\n";
        line_count --;
        break;
      }
      if (event == "BottleneckRate"){
        std::cerr << event << " " << Simulator::Now ().GetMicroSeconds () / (double) 1000000 << " " << value << "\n";
        Simulator::Schedule(Seconds (0.001), &changeBottleneckRate, value);
      }
      if (event == "EndSimulation"){
        Simulator::Stop ();
      }
    }
  }
  live_event_index = line_count;
  Simulator::Schedule (Seconds (1), &CheckLiveEvents, liveEventFilePath);
  efile.close();
}

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
  cmd.AddValue ("segmentDuration", "The duration of a video segment in microseconds", segmentDuration);
  cmd.AddValue ("pandaClients", "The nr of clients using panda", pandaClients);
  cmd.AddValue ("tobascoClients", "The nr of clients using tobasco", tobascoClients);
  cmd.AddValue ("festiveClients", "The nr of clients using festive", festiveClients);
  cmd.AddValue ("segmentSizeFile", "The relative path (from ns-3.x directory) to the file containing the segment sizes in bytes", segmentSizeFilePath);
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

  if (numberOfClients != pandaClients + tobascoClients + festiveClients){
    std::cerr << "clients per algorithm doesn't match nr of clients!" << "\n";
    return -1;
  }
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", StringValue (tcpModel));
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

  // install packet sniffer for logging on router
  routerdevices.Get (0)->TraceConnectWithoutContext ("Sniffer", MakeCallback(&LogPacket));

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
  
  // ns3::Ipv4GlobalRoutingHelper::PopulateRoutingTables();


  // Ipv4AddressHelper address;
  // address.SetBase ("76.1.1.0", "255.255.255.0");
  // Ipv4InterfaceContainer interfaces = address.Assign (devices);
  // Address serverAddress = Address(interfaces.GetAddress (0));

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

  // create logfile for router throughput
  
  std::string Log = dashLogDirectory + simulationName + "/" + ToString(numberOfClients)  + "/sim" + ToString(simulationId) + "_" + "router_output.txt";
  dataLog.open (Log.c_str ());
  dataLog << "Time_Now;Throughput;\n";
  dataLog.flush ();

  // load scheduled events
  ScheduleEvents((dirstr + "sim" + ToString(simulationId) + "_event_schedule.txt").c_str());

  if (liveInputs != 0){
    CheckLiveEvents((dirstr + "sim" + ToString(simulationId) + "_real_time_events.txt"));
  }

  // create logfile for event logging
  
  Log = dashLogDirectory + simulationName + "/" + ToString(numberOfClients)  + "/sim" + ToString(simulationId) + "_" + "event_log.txt";
  eventLog.open (Log.c_str ());
  eventLog << "Time_Now;Event;Value\n";
  eventLog.flush ();
  

  uint clientsPerServer = numberOfClients / numberOfServers;
  for (uint i = 0; i < serverNodes.GetN (); i++)
    {
      TcpStreamServerHelper serverHelper (port);
      ApplicationContainer serverApps = serverHelper.Install (serverNodes.Get (i));
      serverApps.Start (Seconds (1.0));

      TcpStreamClientHelper clientHelper (serverifs.GetAddress (i), port);
      clientHelper.SetAttribute ("SegmentDuration", UintegerValue (segmentDuration));
      clientHelper.SetAttribute ("SegmentSizeFilePath", StringValue (segmentSizeFilePath));
      clientHelper.SetAttribute ("NumberOfClients", UintegerValue(numberOfClients));
      clientHelper.SetAttribute ("SimulationId", UintegerValue (simulationId));
      clientHelper.SetAttribute ("SimulationName", StringValue (simulationName));
      
      std::vector <std::pair <Ptr<Node>, std::string> > clients;

      if (i < serverNodes.GetN () - 1) {
        for (uint j = 0; j < clientsPerServer; j++)
          {
            //add client algorithm pairs for client helper
            uint16_t client_id = i * clientsPerServer + j;
            std::pair <Ptr<Node>, std::string> client (clientNodes.Get (client_id), GetAdaptionAlgo(client_id));
            clients.push_back (client);
          }
      } else{
        for (uint j = 0; j < numberOfClients - clientsPerServer * i; j++)
          {
            uint16_t client_id = i * clientsPerServer + j;
            std::pair <Ptr<Node>, std::string> client (clientNodes.Get (client_id), GetAdaptionAlgo(client_id));
            clients.push_back (client);
          }
      }
      ApplicationContainer clientApp = clientHelper.Install (clients, i * clientsPerServer);
      clientApp.Start (Seconds (2.0));
    }

 
  
  NS_LOG_INFO ("Run Simulation.");
  NS_LOG_INFO ("Sim: " << simulationId << "Clients: " << numberOfClients);
  Simulator::Run ();
  Simulator::Destroy ();
  dataLog.close();
  eventLog.close();
  NS_LOG_INFO ("Done.");
  return 0;
}
