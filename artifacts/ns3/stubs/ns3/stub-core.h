// Minimal stand-ins for the ns-3 headers the scenario includes.
//
// This is NOT ns-3. It exists so that the scenario can be syntax-checked with
// a plain compiler on a machine where ns-3 is not built, which catches the
// mistakes a rewrite can introduce: syntax errors, undeclared names, wrong
// argument counts, wrong types. It cannot catch a mismatch against the real
// ns-3 API, which is what building ns-3 itself is for.
//
// The stubs mirror the signatures the scenario uses, so a call that compiles
// here compiles against the real headers too, as far as arity and type are
// concerned.

#pragma once

#include <cstdint>
#include <cmath>
#include <string>
#include <vector>

#define NS_LOG_COMPONENT_DEFINE(name)
#define NS_LOG_COMPONENT_ENUM(name)

namespace ns3
{

class Time
{
  public:
    double m_s{0.0};
    double GetSeconds() const
    {
        return m_s;
    }
};

inline Time Seconds(double v)
{
    Time t;
    t.m_s = v;
    return t;
}

inline Time Seconds(int v)
{
    Time t;
    t.m_s = v;
    return t;
}

class Vector
{
  public:
    double x{0.0};
    double y{0.0};
    double z{0.0};
    Vector() = default;
    Vector(double xx, double yy, double zz) : x(xx), y(yy), z(zz)
    {
    }
};

template <typename T>
class Ptr
{
  public:
    T* m_p{nullptr};
    Ptr() = default;
    Ptr(T* p) : m_p(p)
    {
    }
    T* operator->() const
    {
        return m_p;
    }
    T& operator*() const
    {
        return *m_p;
    }
    explicit operator bool() const
    {
        return m_p != nullptr;
    }
    template <typename U>
    Ptr<U> GetObject() const
    {
        return Ptr<U>();
    }
};

class Object
{
  public:
    virtual ~Object() = default;
};

class MobilityModel : public Object
{
  public:
    virtual Vector GetPosition() const
    {
        return Vector();
    }
    virtual void SetPosition(Vector position)
    {
        (void)position;
    }
};

class PositionAllocator : public Object
{
  public:
};

class AttributeValue
{
  public:
    AttributeValue() = default;
    explicit AttributeValue(const std::string& v) : m_value(v)
    {
    }
    std::string m_value;
};

class StringValue : public AttributeValue
{
  public:
    explicit StringValue(const std::string& v)
        : AttributeValue(v)
    {
    }
};

class DoubleValue : public AttributeValue
{
  public:
    explicit DoubleValue(double v)
        : AttributeValue(std::to_string(v))
    {
    }
};

class PointerValue : public AttributeValue
{
  public:
    explicit PointerValue(const Ptr<PositionAllocator>& v)
        : AttributeValue()
    {
        (void)v;
    }
};

class UintegerValue : public AttributeValue
{
  public:
    explicit UintegerValue(uint32_t v)
        : AttributeValue(std::to_string(v))
    {
    }
};

class TimeValue : public AttributeValue
{
  public:
    explicit TimeValue(Time v)
        : AttributeValue(std::to_string(v.GetSeconds()))
    {
    }
};

class ObjectFactory
{
  public:
    void SetTypeId(const std::string& id)
    {
        m_id = id;
    }
    void Set(const std::string& name, const AttributeValue& value)
    {
        (void)name;
        (void)value;
    }
    Ptr<Object> Create() const
    {
        return Ptr<Object>();
    }
    std::string m_id;
};

class Node : public Object
{
  public:
    template <typename U>
    Ptr<U> GetObject() const
    {
        return Ptr<U>();
    }
};

class NodeContainer
{
  public:
    uint32_t GetN() const
    {
        return 0;
    }
    Ptr<Node> Get(uint32_t) const
    {
        return Ptr<Node>();
    }
    void Create(uint32_t)
    {
    }
};

class MobilityHelper
{
  public:
    void SetMobilityModel(const std::string& type,
                          const AttributeValue& v1 = AttributeValue(),
                          const AttributeValue& v2 = AttributeValue(),
                          const AttributeValue& v3 = AttributeValue(),
                          const AttributeValue& v4 = AttributeValue())
    {
        (void)type;
        (void)v1;
        (void)v2;
        (void)v3;
        (void)v4;
    }
    void Install(NodeContainer&)
    {
    }
};

class NetDeviceContainer
{
  public:
};

class YansWifiChannelHelper
{
  public:
    static YansWifiChannelHelper Default()
    {
        return YansWifiChannelHelper();
    }
    Ptr<Object> Create() const
    {
        return Ptr<Object>();
    }
};

class YansWifiPhyHelper
{
  public:
    void SetChannel(const Ptr<Object>&)
    {
    }
    void Set(const std::string&, const AttributeValue&)
    {
    }
};

class WifiMacHelper
{
  public:
    void SetType(const std::string&)
    {
    }
};

class WifiHelper
{
  public:
    void SetStandard(int)
    {
    }
    NetDeviceContainer Install(const YansWifiPhyHelper&,
                               const WifiMacHelper&,
                               NodeContainer&) const
    {
        return NetDeviceContainer();
    }
};

class InternetStackHelper
{
  public:
    void Install(NodeContainer&)
    {
    }
};

class Ipv4Address
{
  public:
    Ipv4Address() = default;
};

class Ipv4InterfaceContainer
{
  public:
    Ipv4Address GetAddress(uint32_t) const
    {
        return Ipv4Address();
    }
};

class Ipv4AddressHelper
{
  public:
    void SetBase(const std::string&, const std::string&)
    {
    }
    Ipv4InterfaceContainer Assign(const NetDeviceContainer&) const
    {
        return Ipv4InterfaceContainer();
    }
};

class ApplicationContainer
{
  public:
    void Start(Time)
    {
    }
    void Stop(Time)
    {
    }
};

class UdpEchoServerHelper
{
  public:
    explicit UdpEchoServerHelper(uint16_t)
    {
    }
    ApplicationContainer Install(Ptr<Node>) const
    {
        return ApplicationContainer();
    }
};

class UdpEchoClientHelper
{
  public:
    UdpEchoClientHelper(Ipv4Address, uint16_t)
    {
    }
    void SetAttribute(const std::string&, const AttributeValue&)
    {
    }
    ApplicationContainer Install(Ptr<Node>) const
    {
        return ApplicationContainer();
    }
};

class Simulator
{
  public:
    static Time Now()
    {
        return Time();
    }
    template <typename... Args>
    static void Schedule(Time, void (*)(Args...), Args...)
    {
    }
    static void Stop(Time)
    {
    }
    static void Run()
    {
    }
    static void Destroy()
    {
    }
};

class CommandLine
{
  public:
    explicit CommandLine(const char*)
    {
    }
    template <typename T>
    void AddValue(const std::string&, const std::string&, T&)
    {
    }
    void Parse(int, char**)
    {
    }
};

class RngSeedManager
{
  public:
    static void SetSeed(uint32_t)
    {
    }
    static void SetRun(uint32_t)
    {
    }
};

class Config
{
  public:
    template <typename F2>
    static void Connect(const std::string&, F2)
    {
    }
};

class Packet
{
  public:
};

template <typename F, typename... Args>
F
MakeCallback(F f)
{
    return f;
}

// The bound-argument form, which ns-3 provides for free functions. ns-3
// passes the bound arguments before the trace source's own arguments, so the
// callback's first parameter is the bound one.
template <typename F, typename... Args>
F
MakeBoundCallback(F f, Args...)
{
    return f;
}

} // namespace ns3

#define WIFI_STANDARD_80211b 0
