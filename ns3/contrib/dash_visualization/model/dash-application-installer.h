#ifndef DASH_APPLICATION_INSTALLER_H
#define DASH_APPLICATION_INSTALLER_H

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

class DashApplicationInstaller{

std::string m_clientFilePath;
uint16_t m_port;
uint32_t m_simulationId;
std::string m_simulationName;

public:
    
    DashApplicationInstaller(const std::string& clientFilePath, uint16_t port, uint32_t simulationId, const std::string& simulationName);
    void InstallClients(ns3::NodeContainer clientNodes, ns3::NodeContainer serverNodes, ns3::Ipv4InterfaceContainer serverifs);
    void InstallServers(ns3::NodeContainer serverNodes);
};

} //namespace ns3

#endif //DASH_APPLICATION_INSTALLER_H