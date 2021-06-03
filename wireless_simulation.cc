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
InstallClients (const std::string& clientFilePath, ns3::NodeContainer clientNodes, ns3::NodeContainer serverNodes, ns3::Ipv4InterfaceContainer serverifs, uint16_t port, uint32_t simulationId, const std::string& simulationName){
  std::cerr << "called " << simulationName << std::to_string(simulationId) <<"\n";
  std::ifstream cfile(clientFilePath);
  std::string line;
  uint64_t clientCount = 0;
  uint64_t clientsPerServer = clientNodes.GetN () / serverNodes.GetN ();
  while (std::getline(cfile, line))
  {
    uint64_t server = clientCount / clientsPerServer;
    // read next client batch from file
    std::istringstream iss(line);
    uint amount;
    std::string algo;
    std::string video;
    uint segDuration;
    if (!(iss >> amount >> algo >> video >> segDuration)) {
      std::cerr << "invalid client file!" << "\n";
    }
    video = "./DashVideos/" + video;
    segDuration = segDuration * 1000000;
    std::cerr << std::to_string(amount) << " " << algo << " " << video << " " << std::to_string(segDuration) << "\n";
    //install all clients from this batch
    std::vector <std::pair <Ptr<Node>, std::string> > clients;
    uint offset = clientCount;

    TcpStreamClientHelper clientHelper (serverifs.GetAddress (server), port);
    clientHelper.SetAttribute ("SegmentDuration", UintegerValue (segDuration));
    clientHelper.SetAttribute ("SegmentSizeFilePath", StringValue (video));
    clientHelper.SetAttribute ("NumberOfClients", UintegerValue(clientNodes.GetN ()));
    clientHelper.SetAttribute ("SimulationId", UintegerValue (simulationId));
    clientHelper.SetAttribute ("SimulationName", StringValue (simulationName));
    for (uint i = 0; i < amount; i ++){
      std::pair <Ptr<Node>, std::string> client (clientNodes.Get (clientCount), algo);
      clients.push_back (client);
      clientCount ++;
      if (clientCount / clientsPerServer > server){
        clientHelper.SetAttribute ("RemoteAddress", AddressValue (serverifs.GetAddress (server)));
      }
    }

    ApplicationContainer clientApp = clientHelper.Install (clients, offset);
    clientApp.Start (Seconds (2.0));
  }
  cfile.close();

  //Install server applications
  for (uint i = 0; i < serverNodes.GetN (); i++)
    {
      TcpStreamServerHelper serverHelper (port);
      ApplicationContainer serverApps = serverHelper.Install (serverNodes.Get (i));
      serverApps.Start (Seconds (1.0));
    }
}

void
ScheduleEvents (const char* eventFilePath)
{
  std::cerr << "called " << eventFilePath <<"\n";
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
    if (event == "BottleneckRate"){
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
  bool shortGuardInterval = true;

  TypeId tcpTid;
  NS_ABORT_MSG_UNLESS (TypeId::LookupByNameFailSafe (tcpModel, &tcpTid), "TypeId " << tcpModel << " not found");
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", TypeIdValue (TypeId::LookupByName (tcpModel)));
  Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue (1446));
  Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue (524288));
  Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue (524288));

  // set up wifi
  WifiHelper wifiHelper;
  wifiHelper.SetStandard (WIFI_PHY_STANDARD_80211n_5GHZ);
  wifiHelper.SetRemoteStationManager ("ns3::MinstrelHtWifiManager");//


  /* Set up Legacy Channel */
  YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default ();
  // We do not set an explicit propagation loss model here, we just use the default ones that get applied with the building model.

  /* Setup Physical Layer */
  YansWifiPhyHelper wifiPhy = YansWifiPhyHelper::Default ();
  wifiPhy.SetPcapDataLinkType (YansWifiPhyHelper::DLT_IEEE802_11_RADIO);
  wifiPhy.Set ("TxPowerStart", DoubleValue (20.0));//
  wifiPhy.Set ("TxPowerEnd", DoubleValue (20.0));//
  wifiPhy.Set ("TxPowerLevels", UintegerValue (1));//
  wifiPhy.Set ("TxGain", DoubleValue (0));//
  wifiPhy.Set ("RxGain", DoubleValue (0));//
  wifiPhy.SetErrorRateModel ("ns3::YansErrorRateModel");//
  wifiPhy.SetChannel (wifiChannel.Create ());
  wifiPhy.Set("ShortGuardEnabled", BooleanValue(shortGuardInterval));
  wifiPhy.Set ("Antennas", UintegerValue (4));


  //Create nodes

  ns3::NodeContainer routerNodes;
  routerNodes.Create(2);
  ns3::NodeContainer clientNodes;
  clientNodes.Create(numberOfClients);
  ns3::NodeContainer serverNodes;
  serverNodes.Create(numberOfServers);

  ns3::NodeContainer wifiNodes;
  wifiNodes.Add (routerNodes.Get(0));
  wifiNodes.Add (clientNodes);

  
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

  
  /* create MAC layers */
  WifiMacHelper wifiMac;
  /* WLAN configuration */
  Ssid ssid = Ssid ("network");
  /* Configure STAs for WLAN*/

  wifiMac.SetType ("ns3::StaWifiMac",
                    "Ssid", SsidValue (ssid));
  NetDeviceContainer staDevices;
  staDevices = wifiHelper.Install (wifiPhy, wifiMac, clientNodes);

  /* Configure AP for WLAN*/
  wifiMac.SetType ("ns3::ApWifiMac",
                    "Ssid", SsidValue (ssid));
  NetDeviceContainer apDevice;
  apDevice = wifiHelper.Install (wifiPhy, wifiMac, routerNodes.Get (0));



  Config::Set ("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phy/ChannelWidth", UintegerValue (40));

  /* Determin WLAN devices (AP and STAs) */
  NetDeviceContainer wlanDevices;
  wlanDevices.Add (staDevices);
  wlanDevices.Add (apDevice);

  
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
  ns3::Ipv4AddressHelper serverips =
      ns3::Ipv4AddressHelper("10.16.0.0", "255.255.255.0");

  ns3::Ipv4InterfaceContainer routerifs;
  ns3::Ipv4InterfaceContainer serverifs;
  ns3::Ipv4InterfaceContainer rightrouterifs;

  // assign addresses to connection connecting routers
  routerifs = routerips.Assign(routerdevices);

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

  /* Assign IP addresses */
  Ipv4AddressHelper address;

  address.SetBase ("10.8.0.0", "255.255.255.0");
  address.Assign (wlanDevices);

 /* Populate routing table */
  Ipv4GlobalRoutingHelper::PopulateRoutingTables ();
  uint16_t port = 9;


//////////////////////////////////////////////////////////////////////////////////////////////////
//// Set up Building
//////////////////////////////////////////////////////////////////////////////////////////////////
  double roomHeight = 3;
  double roomLength = 6;
  double roomWidth = 5;
  uint32_t xRooms = 8;
  uint32_t yRooms = 3;
  uint32_t nFloors = 6;

  Ptr<Building> b = CreateObject <Building> ();
  b->SetBoundaries (Box ( 0.0, xRooms * roomWidth,
                          0.0, yRooms * roomLength,
                          0.0, nFloors * roomHeight));
  b->SetBuildingType (Building::Office);
  b->SetExtWallsType (Building::ConcreteWithWindows);
  b->SetNFloors (6);
  b->SetNRoomsX (8);
  b->SetNRoomsY (3);

  Vector posAp = Vector ( 1.0, 1.0, 1.0);

  /* Set up positions of nodes (AP and server) */
  Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator> ();
  positionAlloc->Add (posAp);
  


  Ptr<RandomRoomPositionAllocator> randPosAlloc = CreateObject<RandomRoomPositionAllocator> ();
  randPosAlloc->AssignStreams (simulationId);


  // create folder for logged data
  const char * mylogsDir = dashLogDirectory.c_str();
  mkdir (mylogsDir, 0775);
  std::string algodirstr (dashLogDirectory +  simulationName );  
  const char * algodir = algodirstr.c_str();
  mkdir (algodir, 0775);
  std::string dirstr (dashLogDirectory + simulationName + "/" + ToString (numberOfClients) + "/");
  const char * dir = dirstr.c_str();
  mkdir(dir, 0775);

  std::ofstream clientPosLog;
  std::string clientPos = dashLogDirectory + simulationName + "/" + ToString (numberOfClients) + "/" + "sim" + ToString (simulationId) + "_"  + "clientPos.txt";
  clientPosLog.open (clientPos.c_str());
  NS_ASSERT_MSG (clientPosLog.is_open(), "Couldn't open clientPosLog file");

  // allocate clients to positions
  for (uint i = 0; i < numberOfClients; i++)
    {
      Vector pos = Vector (randPosAlloc->GetNext());
      positionAlloc->Add (pos);

      // log client positions
      clientPosLog << ToString(pos.x) << ", " << ToString(pos.y) << ", " << ToString(pos.z) << "\n";
      clientPosLog.flush ();
    }


  MobilityHelper mobility;
  mobility.SetPositionAllocator (positionAlloc);
  mobility.SetMobilityModel ("ns3::ConstantPositionMobilityModel");
  // install all of the nodes that have been added to positionAlloc to the mobility model
  mobility.Install (wifiNodes);
  BuildingsHelper::Install (wifiNodes); // networkNodes contains all nodes, stations and ap
  BuildingsHelper::MakeMobilityModelConsistent ();
 

  // load scheduled events
  ScheduleEvents((dirstr + "sim" + ToString(simulationId) + "_event_schedule.txt").c_str());

  if (liveInputs != 0){
    CheckLiveEvents((dirstr + "sim" + ToString(simulationId) + "_real_time_events.txt"));
  }

  // create logfile for event logging
  std::string Log = dashLogDirectory + simulationName + "/" + ToString(numberOfClients)  + "/sim" + ToString(simulationId) + "_" + "event_log.txt";
  eventLog.open (Log.c_str ());
  eventLog << "Time_Now;Event;Value\n";
  eventLog.flush ();
  

  InstallClients((dirstr + "sim" + ToString(simulationId) + "_clients.txt"), clientNodes, serverNodes, serverifs, port, simulationId, simulationName);

  Simulator::Stop(Seconds (3600));
  LogEvent ("BottleneckRate", std::stoi(bottleNeckRate));
  NS_LOG_INFO ("Run Simulation.");
  NS_LOG_INFO ("Sim: " << simulationId << "Clients: " << numberOfClients);
  Simulator::Run ();
  Simulator::Destroy ();
  dataLog.close();
  eventLog.close();
  NS_LOG_INFO ("Done.");
  return 0;
}
