#ifndef DASH_EVENT_SCHEDULER_H
#define DASH_EVENT_SCHEDULER_H

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

class DashEventScheduler{

uint64_t live_event_index;
std::ofstream eventLog;

public:
    
    DashEventScheduler(const std::string& eventLogPath, const std::string& liveEventFilePath, u_int32_t liveInputs);
    void LogEvent (const char *event ,uint64_t value);
    void changeBottleneckRate (const std::string& value);
    void ScheduleEvents (const char* eventFilePath);
    void CheckLiveEvents (const std::string& liveEventFilePath);
    void CleanUp ();
};

} //namespace ns3

#endif //DASH_APPLICATION_INSTALLER_H