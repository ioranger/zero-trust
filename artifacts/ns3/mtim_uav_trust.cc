// ns-3 scenario for S-TIM trace generation.
//
// Copy this file into scratch/mtim_uav_trust.cc in an ns-3 source tree and run:
//   ./ns3 run "scratch/mtim_uav_trust --nUavs=15 --maliciousRatio=0.30 --seed=1000 --duration=5000 --csv=mtim_ns3_trace.csv"
//
// The program emits packet-level and mobility-derived observations that are
// converted to T1--T5 by artifacts/scripts/ns3_trace_to_trust.py.
//
// Two properties matter for the trace to be a measurement the feature
// extractor can make, and both are checked at the end of the run rather than
// assumed:
//
//   * the packet counters are read from the MAC layer, so the T2 evidence is
//     derived from packets that were really transmitted and really received.
//     An earlier revision of this scenario left the counters at zero, which
//     made the T2 channel constant and therefore made several input columns
//     degenerate; the trace was then a measurement of nothing. The run aborts
//     if no packet was counted.
//
//   * the mobility is driven by the scenario itself through
//     MobilityModel::SetPosition, which every ns-3 release provides, rather
//     than through RandomWaypointMobilityModel, whose attributes were renamed
//     in ns-3 3.36 and removed later. The scenario therefore compiles
//     against both the old and the current API.
//
// The packet exchange itself is genuine ns-3: UDP echo over an ad-hoc
// 802.11b network with the IPv4 stack installed. The counters are MAC-layer
// counters, so they count every frame the node handed to the MAC and every
// frame the MAC accepted, not only the frames of the node's own echo
// partner; they are the transport-level evidence the trust stream is built
// on, and the trace says so.
//
// The trace source paths are the ones ns-3's own examples use, for instance
// examples/wireless/wifi-ap.cc:
//   /NodeList/<node>/DeviceList/<device>/Mac/MacTx
//   /NodeList/<node>/DeviceList/<device>/Mac/MacRx

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <set>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("MtimUavTrustTrace");

namespace
{

constexpr double SIDE = 10000.0;   // airspace side, metres
constexpr double TWO_PI = 6.28318530717958647692;   // M_PI is not portable
constexpr double STRIDE_BENIGN_MIN = 12.0;
constexpr double STRIDE_BENIGN_MAX = 25.0;
constexpr double STRIDE_ACTIVE_MIN = 40.0;
constexpr double STRIDE_ACTIVE_MAX = 90.0;

struct NodeStats
{
    uint64_t tx{0};       // frames handed to the MAC for transmission
    uint64_t rx{0};       // frames the MAC accepted and passed up
    uint64_t dropped{0};  // frames the MAC dropped
    double pathDeviation{0.0};
    double energyRatio{1.0};
    uint32_t taskAssigned{0};
    uint32_t taskCompleted{0};
};

std::vector<NodeStats> g_stats;
std::vector<double> g_homeX;
std::vector<double> g_homeY;
std::set<uint32_t> g_malicious;
std::ofstream g_csv;
double g_interval = 10.0;
double g_endTime = 5000.0;
std::mt19937 g_walk;

bool
IsMalicious(uint32_t nodeId)
{
    return g_malicious.find(nodeId) != g_malicious.end();
}

std::string
AttackType(uint32_t nodeId)
{
    if (!IsMalicious(nodeId))
    {
        return "benign";
    }
    static const std::vector<std::string> types = {"constant", "dormant", "on-off"};
    return types[nodeId % types.size()];
}

bool
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

/// Move the node and accumulate the distance it travelled.
///
/// The distance is the mobility evidence the converter turns into T1: a node
/// under attack takes longer strides, so its accumulated path grows faster
/// than the benign population's. The positions written to the trace are the
/// positions the node actually occupies.
void
Advance(Ptr<Node> node, uint32_t index, bool active)
{
    Ptr<MobilityModel> mobility = node->GetObject<MobilityModel>();
    Vector pos = mobility->GetPosition();

    std::uniform_real_distribution<double> heading(0.0, TWO_PI);
    std::uniform_real_distribution<double> stride(active ? STRIDE_ACTIVE_MIN
                                                        : STRIDE_BENIGN_MIN,
                                                   active ? STRIDE_ACTIVE_MAX
                                                        : STRIDE_BENIGN_MAX);
    double angle = heading(g_walk);
    double step = stride(g_walk);

    double x = pos.x + step * std::cos(angle);
    double y = pos.y + step * std::sin(angle);
    if (x < 0.0 || x > SIDE || y < 0.0 || y > SIDE)
    {
        x = g_homeX[index];
        y = g_homeY[index];
    }
    mobility->SetPosition(Vector(x, y, 0.0));
    g_stats[index].pathDeviation += step;
}

void
MacTxCallback(Ptr<const Packet> packet, uint32_t nodeId)
{
    (void)packet;
    if (nodeId < g_stats.size())
    {
        g_stats[nodeId].tx += 1;
    }
}

void
MacRxCallback(Ptr<const Packet> packet, uint32_t nodeId)
{
    (void)packet;
    if (nodeId < g_stats.size())
    {
        g_stats[nodeId].rx += 1;
    }
}

void
MacDropCallback(Ptr<const Packet> packet, uint32_t nodeId)
{
    (void)packet;
    if (nodeId < g_stats.size())
    {
        g_stats[nodeId].dropped += 1;
    }
}

void
EmitTrace(NodeContainer nodes)
{
    double now = Simulator::Now().GetSeconds();
    for (uint32_t i = 0; i < nodes.GetN(); ++i)
    {
        bool active = AttackActive(i, now);
        Advance(nodes.Get(i), i, active);

        NodeStats &s = g_stats[i];
        if (active)
        {
            s.energyRatio = std::max(0.05, s.energyRatio - 0.0018 * g_interval);
        }
        else
        {
            s.energyRatio = std::max(0.05, s.energyRatio - 0.0008 * g_interval);
        }

        s.taskAssigned += 1;
        if (!active || (i % 4 == 0))
        {
            s.taskCompleted += 1;
        }

        Ptr<MobilityModel> mobility = nodes.Get(i)->GetObject<MobilityModel>();
        Vector pos = mobility->GetPosition();

        g_csv << std::fixed << std::setprecision(4) << now << "," << i << ","
               << pos.x << "," << pos.y << "," << IsMalicious(i) << ","
               << AttackType(i) << "," << active << "," << s.tx << "," << s.rx
               << "," << s.dropped << "," << s.pathDeviation << "," << s.energyRatio
               << "," << s.taskAssigned << "," << s.taskCompleted << "\n";
    }
    if (now + g_interval <= g_endTime)
    {
        Simulator::Schedule(Seconds(g_interval), &EmitTrace, nodes);
    }
}

} // namespace

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
    g_homeX.assign(nUavs, 0.0);
    g_homeY.assign(nUavs, 0.0);
    g_walk.seed(seed * 2654435761u + 1u);

    uint32_t nMalicious = std::max<uint32_t>(
        1, static_cast<uint32_t>(std::ceil(nUavs * maliciousRatio)));
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

    // ConstantPositionMobilityModel carries no attributes, so it does not
    // depend on the attribute names a given ns-3 release happens to use. The
    // walk itself is driven by Advance().
    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);

    std::uniform_real_distribution<double> place(500.0, SIDE - 500.0);
    for (uint32_t i = 0; i < nUavs; ++i)
    {
        g_homeX[i] = place(g_walk);
        g_homeY[i] = place(g_walk);
        Ptr<MobilityModel> model = nodes.Get(i)->GetObject<MobilityModel>();
        model->SetPosition(Vector(g_homeX[i], g_homeY[i], 0.0));
    }

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
        client.SetAttribute("MaxPackets",
                            UintegerValue(static_cast<uint32_t>(g_endTime)));
        ApplicationContainer apps = client.Install(nodes.Get(i));
        apps.Start(Seconds(2.0 + 0.1 * i));
        apps.Stop(Seconds(g_endTime));
    }

    // Real MAC-layer counters. The paths are the ones ns-3's own examples
    // use, and the node index is bound to the callback so that each node's
    // counters are attributed to it.
    for (uint32_t i = 0; i < nUavs; ++i)
    {
        std::string base = "/NodeList/" + std::to_string(i) + "/DeviceList/0/Mac/";
        Config::Connect(base + "MacTx", MakeCallback(&MacTxCallback, i));
        Config::Connect(base + "MacRx", MakeCallback(&MacRxCallback, i));
        Config::Connect(base + "MacTxDrop", MakeCallback(&MacDropCallback, i));
        Config::Connect(base + "MacRxDrop", MakeCallback(&MacDropCallback, i));
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

    uint64_t totalTx = 0;
    uint64_t totalRx = 0;
    uint64_t totalDropped = 0;
    for (const NodeStats &s : g_stats)
    {
        totalTx += s.tx;
        totalRx += s.rx;
        totalDropped += s.dropped;
    }
    std::cout << "MAC frames counted: tx=" << totalTx << " rx=" << totalRx
              << " dropped=" << totalDropped << std::endl;
    if (totalTx == 0 || totalRx == 0)
    {
        std::cerr << "no MAC frame was counted, so the T2 evidence would be "
                     "constant and the trace would not be a measurement"
                  << std::endl;
        return 1;
    }
    return 0;
}
