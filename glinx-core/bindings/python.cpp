#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include "glinx/buffer.hpp"
#include "glinx/ipc.hpp"

namespace nb = nanobind;
using namespace nb::literals;
using namespace glinx;

NB_MODULE(_glinx_core, m) {
    m.doc() = "Glinx C++ core - High-performance hardware ingestion";

    // SensorMessage
    nb::class_<SensorMessage>(m, "SensorMessage")
        .def(nb::init<>())
        .def_rw("source_id", &SensorMessage::source_id)
        .def_rw("protocol", &SensorMessage::protocol)
        .def_rw("timestamp", &SensorMessage::timestamp)
        .def_rw("payload_size", &SensorMessage::payload_size)
        .def_prop_rw("payload",
            [](const SensorMessage& self) {
                return nb::bytes(reinterpret_cast<const char*>(self.payload), self.payload_size);
            },
            [](SensorMessage& self, const nb::bytes& data) {
                size_t size = std::min(data.size(), sizeof(self.payload));
                std::memcpy(self.payload, data.c_str(), size);
                self.payload_size = size;
            })
        .def("to_dict", [](const SensorMessage& self) {
            nb::dict d;
            d["source_id"] = std::string(self.source_id);
            d["protocol"] = std::string(self.protocol);
            d["timestamp"] = self.timestamp;
            d["payload"] = nb::bytes(reinterpret_cast<const char*>(self.payload), self.payload_size);
            return d;
        });

    // SensorBuffer
    nb::class_<SensorBuffer>(m, "SensorBuffer")
        .def(nb::init<size_t>(), "capacity"_a = 16384)
        .def("push", &SensorBuffer::push, "msg"_a)
        .def("drain", &SensorBuffer::drain)
        .def("size", &SensorBuffer::size)
        .def("empty", &SensorBuffer::empty)
        .def("total_pushed", &SensorBuffer::total_pushed)
        .def("total_dropped", &SensorBuffer::total_dropped)
        .def("stats", [](const SensorBuffer& self) {
            nb::dict d;
            d["size"] = self.size();
            d["total_pushed"] = self.total_pushed();
            d["total_dropped"] = self.total_dropped();
            return d;
        });

    // GlinxRuntime
    nb::class_<GlinxRuntime>(m, "GlinxRuntime")
        .def(nb::init<const std::string&>(), "config_json"_a)
        .def("start", &GlinxRuntime::start)
        .def("stop", &GlinxRuntime::stop)
        .def("get_messages", &GlinxRuntime::get_messages)
        .def("get_stats", [](const GlinxRuntime& self) {
            return self.get_stats().dump();
        })
        .def("__enter__", [](GlinxRuntime& self) -> GlinxRuntime& {
            self.start();
            return self;
        })
        .def("__exit__", [](GlinxRuntime& self, nb::object, nb::object, nb::object) {
            self.stop();
        });

    // Module-level functions
    m.def("version", []() {
        return "0.1.0";
    });

    m.def("benchmark_buffer", [](size_t iterations) {
        SensorBuffer buffer;
        SensorMessage msg;
        std::strncpy(msg.source_id, "bench", sizeof(msg.source_id) - 1);
        std::strncpy(msg.protocol, "mock", sizeof(msg.protocol) - 1);
        msg.timestamp = 0.0;
        msg.payload_size = 64;

        auto start = std::chrono::high_resolution_clock::now();
        
        for (size_t i = 0; i < iterations; ++i) {
            buffer.push(msg);
        }
        
        auto mid = std::chrono::high_resolution_clock::now();
        auto messages = buffer.drain();
        auto end = std::chrono::high_resolution_clock::now();

        auto push_us = std::chrono::duration_cast<std::chrono::microseconds>(mid - start).count();
        auto drain_us = std::chrono::duration_cast<std::chrono::microseconds>(end - mid).count();

        nb::dict result;
        result["iterations"] = iterations;
        result["push_time_us"] = push_us;
        result["drain_time_us"] = drain_us;
        result["push_rate_mhz"] = (iterations / static_cast<double>(push_us));
        result["drain_rate_mhz"] = (messages.size() / static_cast<double>(drain_us));
        result["messages_drained"] = messages.size();
        
        return result;
    }, "iterations"_a);
}
