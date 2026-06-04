// ns-3 scenario for MTIM trace generation.
//
// Copy this file into scratch/mtim_uav_trust.cc in an ns-3 source tree and run:
//   ./ns3 run "scratch/mtim_uav_trust --nUavs=15 --maliciousRatio=0.30 --seed=1000 --csv=mtim_ns3_trace.csv"
//
// The program emits packet-level and mobility-derived observations that are
// converted to T1--T5 by artifacts/scripts/ns3_trace_to_trust.py.

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <random>
#include <set>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("MtimUavTrustTrace");

struct NodeStats
{
  uint32_t tx{0};
  uint32_t rx{0};
  uint32_t dropped{0};
  double pathDeviation{0.0};
  double energyRatio{1.0};
  uint32_t taskAssigned{0};
  uint32_t taskCompleted{0};
};

static std::vector<NodeStats> g_stats;
static std::set<uint32_t> g_malicious;
static std::ofstream g_csv;
static double g_interval = 10.0;
static double g_endTime = 5000.0;

static bool
IsMalicious(uint32_t nodeId)
{
  return g_malicious.find(nodeId) != g_malicious.end();
}

static std::string
AttackType(uint32_t nodeId)
{
  if (!IsMalicious(nodeId))
    {
      return "benign";
    }
  static const std::vector<std::string> types = {"constant", "dormant", "on-off"};
  return types[nodeId % types.size()];
}

static bool
AttackActive(uint32_t nodeId, double now)
{
  std::string type = AttackType(nodeId);
  if (type == "benign")
    {
      return false;
    }
  if (type == "constant")
    {
      return true;
    }
  if (type == "dormant")
    {
      return now >= 1500.0;
    }
  return now >= 1000.0 && (static_cast<uint32_t>((now - 1000.0) / 500.0) % 2 == 0);
}

static void
EmitTrace(NodeContainer nodes)
{
  double now = Simulator::Now().GetSeconds();
  for (uint32_t i = 0; i < nodes.GetN(); ++i)
    {
      Ptr<MobilityModel> mobility = nodes.Get(i)->GetObject<MobilityModel>();
      Vector pos = mobility->GetPosition();
      NodeStats &s = g_stats[i];
      bool active = AttackActive(i, now);
      if (active)
        {
          s.dropped += 1 + (i % 3);
          s.pathDeviation += 7.5 + 0.8 * (i % 5);
          s.energyRatio = std::max(0.05, s.energyRatio - 0.0018 * g_interval);
        }
      else
        {
          s.pathDeviation += 1.2 + 0.2 * (i % 3);
          s.energyRatio = std::max(0.05, s.energyRatio - 0.0008 * g_interval);
        }

      s.taskAssigned += 1;
      if (!active || (i % 4 == 0))
        {
          s.taskCompleted += 1;
        }

      g_csv << std::fixed << std::setprecision(4)
            << now << "," << i << "," << pos.x << "," << pos.y << ","
            << IsMalicious(i) << "," << AttackType(i) << "," << active << ","
            << s.tx << "," << s.rx << "," << s.dropped << ","
            << s.pathDeviation << "," << s.energyRatio << ","
            << s.taskAssigned << "," << s.taskCompleted << "\n";
    }
  if (now + g_interval <= g_endTime)
    {
      Simulator::Schedule(Seconds(g_interval), &EmitTrace, nodes);
    }
}

int
main(int argc, char *argv[])
{
  uint32_t nUavs = 15;
  double maliciousRatio = 0.30;
  uint32_t seed = 1000;
  std::string csv = "mtim_ns3_trace.csv";
  CommandLine cmd(__FILE__);
  cmd.AddValue("nUavs", "Number of UAV nodes", nUavs);
  cmd.AddValue("maliciousRatio", "Fraction of malicious UAVs", maliciousRatio);
  cmd.AddValue("seed", "RNG seed", seed);
  cmd.AddValue("csv", "Output CSV path", csv);
  cmd.AddValue("duration", "Mission duration in seconds", g_endTime);
  cmd.Parse(argc, argv);

  RngSeedManager::SetSeed(seed);
  RngSeedManager::SetRun(seed);
  g_stats.assign(nUavs, NodeStats{});

  uint32_t nMalicious = std::max<uint32_t>(1, static_cast<uint32_t>(std::ceil(nUavs * maliciousRatio)));
  std::vector<uint32_t> ids(nUavs);
  std::iota(ids.begin(), ids.end(), 0);
  std::mt19937 rng(seed);
  std::shuffle(ids.begin(), ids.end(), rng);
  for (uint32_t i = 0; i < nMalicious; ++i)
    {
      g_malicious.insert(ids[i]);
    }

  NodeContainer nodes;
  nodes.Create(nUavs);

  ObjectFactory positionFactory;
  positionFactory.SetTypeId("ns3::RandomRectanglePositionAllocator");
  positionFactory.Set("X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=10000.0]"));
  positionFactory.Set("Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=10000.0]"));
  Ptr<PositionAllocator> positionAllocator = positionFactory.Create()->GetObject<PositionAllocator>();

  MobilityHelper mobility;
  mobility.SetPositionAllocator(positionAllocator);
  mobility.SetMobilityModel("ns3::RandomWaypointMobilityModel",
                            "Speed", StringValue("ns3::UniformRandomVariable[Min=3.0|Max=15.0]"),
                            "Pause", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"),
                            "PositionAllocator", PointerValue(positionAllocator));
  mobility.Install(nodes);

  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211b);
  YansWifiPhyHelper phy;
  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  phy.SetChannel(channel.Create());
  phy.Set("TxPowerStart", DoubleValue(16.0));
  phy.Set("TxPowerEnd", DoubleValue(16.0));
  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");
  NetDeviceContainer devices = wifi.Install(phy, mac, nodes);

  InternetStackHelper internet;
  internet.Install(nodes);
  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  Ipv4InterfaceContainer interfaces = ipv4.Assign(devices);

  uint16_t port = 9000;
  for (uint32_t i = 0; i < nUavs; ++i)
    {
      UdpEchoServerHelper server(port + i);
      ApplicationContainer serverApps = server.Install(nodes.Get(i));
      serverApps.Start(Seconds(1.0));
      serverApps.Stop(Seconds(g_endTime));
    }

  for (uint32_t i = 0; i < nUavs; ++i)
    {
      uint32_t dst = (i + 1) % nUavs;
      UdpEchoClientHelper client(interfaces.GetAddress(dst), port + dst);
      client.SetAttribute("Interval", TimeValue(Seconds(1.0)));
      client.SetAttribute("PacketSize", UintegerValue(128));
      client.SetAttribute("MaxPackets", UintegerValue(static_cast<uint32_t>(g_endTime)));
      ApplicationContainer apps = client.Install(nodes.Get(i));
      apps.Start(Seconds(2.0 + 0.1 * i));
      apps.Stop(Seconds(g_endTime));
    }

  g_csv.open(csv);
  g_csv << "time_s,node_id,x_m,y_m,is_malicious,attack_type,attack_active,"
        << "tx_packets,rx_packets,dropped_packets,path_deviation_m,energy_ratio,"
        << "task_assigned,task_completed\n";
  Simulator::Schedule(Seconds(g_interval), &EmitTrace, nodes);
  Simulator::Stop(Seconds(g_endTime));
  Simulator::Run();
  Simulator::Destroy();
  g_csv.close();

  return 0;
}
