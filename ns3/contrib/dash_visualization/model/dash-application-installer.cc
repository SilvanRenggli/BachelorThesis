#include "dash-application-installer.h"
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

namespace ns3 {

DashApplicationInstaller::DashApplicationInstaller(const std::string& clientFilePath, uint16_t port, uint32_t simulationId, const std::string& simulationName){
    m_clientFilePath = clientFilePath;
    m_port = port;
    m_simulationId = simulationId;
    m_simulationName = simulationName;
}

void
DashApplicationInstaller::InstallClients (ns3::NodeContainer clientNodes, ns3::NodeContainer serverNodes, ns3::Ipv4InterfaceContainer serverifs){
  std::cerr << "called " << m_simulationName << std::to_string(m_simulationId) <<"\n";
  std::ifstream cfile(m_clientFilePath);
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

    TcpStreamClientHelper clientHelper (serverifs.GetAddress (server), m_port);
    clientHelper.SetAttribute ("SegmentDuration", UintegerValue (segDuration));
    clientHelper.SetAttribute ("SegmentSizeFilePath", StringValue (video));
    clientHelper.SetAttribute ("NumberOfClients", UintegerValue(clientNodes.GetN ()));
    clientHelper.SetAttribute ("SimulationId", UintegerValue (m_simulationId));
    clientHelper.SetAttribute ("SimulationName", StringValue (m_simulationName));
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
}

void
DashApplicationInstaller::InstallServers (ns3::NodeContainer serverNodes){
  //Install server applications
  for (uint i = 0; i < serverNodes.GetN (); i++)
    {
      TcpStreamServerHelper serverHelper (m_port);
      ApplicationContainer serverApps = serverHelper.Install (serverNodes.Get (i));
      serverApps.Start (Seconds (1.0));
    }
}

} //namespace ns3