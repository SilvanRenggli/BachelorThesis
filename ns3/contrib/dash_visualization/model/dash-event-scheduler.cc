#include "dash-event-scheduler.h"
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

DashEventScheduler::DashEventScheduler(const std::string& eventLogPath, const std::string& liveEventFilePath ,u_int32_t liveInputs)
{ 
  live_event_index = 0;
  eventLog.open (eventLogPath.c_str ());
  eventLog << "Time_Now;Event;Value\n";
  eventLog.flush ();
  if (liveInputs != 0){
    CheckLiveEvents(liveEventFilePath);
  }
}

void
DashEventScheduler::ScheduleEvents (const char* eventFilePath)
{
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
      Simulator::Schedule(Seconds(time), &DashEventScheduler::changeBottleneckRate, this, value);
    }
  }
  efile.close();
}

void
DashEventScheduler::CheckLiveEvents (const std::string& liveEventFilePath)
{
  std::ifstream efile(liveEventFilePath);
  std::string line;
  uint64_t line_count = 0;
  while (std::getline(efile, line))
  { 
    line_count ++;
    if(line_count > live_event_index){
      std::istringstream iss(line);
      std::string event;
      std::string value;
      if (!(iss >> event >> value)) {
        line_count --;
        break;
      }
      if (event == "BottleneckRate"){
        Simulator::Schedule(Seconds (0.001), &DashEventScheduler::changeBottleneckRate, this, value);
      }
      if (event == "EndSimulation"){
        Simulator::Stop ();
      }
    }
  }
  live_event_index = line_count;
  Simulator::Schedule (Seconds (1), &DashEventScheduler::CheckLiveEvents, this,liveEventFilePath);
  efile.close();
}

void
DashEventScheduler::LogEvent (const char *event ,uint64_t value)
{
  eventLog << Simulator::Now ().GetMicroSeconds () / (double) 1000000 << ";" << event << ";" << value << "\n";
  eventLog.flush ();
}

void
DashEventScheduler::changeBottleneckRate (const std::string& value)
{
  Config::Set("/NodeList/0/DeviceList/0/$ns3::PointToPointNetDevice/DataRate", StringValue(value) );
  Config::Set("/NodeList/1/DeviceList/0/$ns3::PointToPointNetDevice/DataRate", StringValue(value) );
  LogEvent ("BottleneckRate", std::stoi(value));
}

void
DashEventScheduler::CleanUp (){
  eventLog.close();
}

} //namespace ns3