// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#include <chrono>
#include <cstdint>
#include <mavsdk/mavsdk.h>
#include <mavsdk/plugins/action/action.h>
#include <mavsdk/plugins/telemetry/telemetry.h>
#include <mavsdk/plugins/shell/shell.h>
#include <mavsdk/plugins/mission/mission.h>
#include <mavsdk/plugins/param/param.h>
#include <mavsdk/plugins/info/info.h>
#include <mavsdk/plugins/mavlink_passthrough/mavlink_passthrough.h>

#include <iostream>
#include <future>
#include <memory>
#include <thread>
#include <cstdlib>

using namespace mavsdk;
using std::chrono::seconds;
using std::chrono::milliseconds;
using std::this_thread::sleep_for;

void usage(const std::string& bin_name)
{
    std::cerr << "Usage : " << bin_name << " <connection_url>\n"
              << "Connection URL format should be :\n"
              << " For TCP : tcp://[server_host][:server_port]\n"
              << " For UDP : udp://[bind_host][:bind_port]\n"
              << " For Serial : serial:///path/to/serial/dev[:baudrate]\n"
              << "For example, to connect to the simulator use URL: udp://:14540\n";
}


std::shared_ptr<System> find_system(
        const Mavsdk& mavsdk,
        std::function<bool(const std::shared_ptr<const System>)> filter)
{
    const auto systems = mavsdk.systems();
    auto sys = std::find_if(systems.cbegin(), systems.cend(), filter);
    if (sys != systems.cend()) return *sys;
    return nullptr;
}

std::shared_ptr<System> get_system(Mavsdk& mavsdk)
{
    std::cout << "Waiting to discover system...\n";
    std::uint32_t tries{60};

    while (tries--)
    {
        if (auto autopilot_system = find_system(mavsdk,
                    [](const auto sys) { return sys->has_autopilot(); });
            autopilot_system)
        {
            std::cout << "Discovered autopilot!\n";
            return autopilot_system;
        }
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    return {};
}

void parameter_change(Param& param, int state) {

        return;
        auto r = param.set_param_int("NAV_RCL_ACT", state);
        if (r != Param::Result::Success) {
            std::cerr << "Parameter set failed: " << r << '\n';
        }
        r = param.set_param_int("NAV_DLL_ACT", state);
        if (r != Param::Result::Success) {
            std::cerr << "Parameter set failed: " << r << '\n';
        }
        r = param.set_param_int("CAL_MAG0_PRIO", 0);
        if (r != Param::Result::Success) {
            std::cerr << "Parameter set failed: " << r << '\n';
        }
        r = param.set_param_int("CAL_MAG1_ROT", 43);
        if (r != Param::Result::Success) {
            std::cerr << "Parameter set failed: " << r << '\n';
        }
}

int main(int argc, char** argv)
{
    if (argc != 2) {
        usage(argv[0]);
        return 1;
    }

    Mavsdk mavsdk;
    ConnectionResult connection_result = mavsdk.add_any_connection(argv[1]);

    if (connection_result != ConnectionResult::Success) {
        std::cerr << "Connection failed: " << connection_result << '\n';
        return 1;
    }

    auto system = get_system(mavsdk);
    if (!system) {
        std::cerr << "Could not find Autopilot!\n";
        return 1;
    }

    // Instantiate plugins.
    auto telemetry = Telemetry{system};
    auto action = Action{system};
    auto shell = Shell{system};
    auto mission = Mission{system};
    auto param = Param{system};
    auto info = Info{system};
    auto mavlink = MavlinkPassthrough{system};

    sleep_for(seconds(5));

    auto mission_download = mission.download_mission();

    if (mission_download.first != Mission::Result::Success) return 1;
    Mission::MissionPlan mission_plan = mission_download.second;


    shell.subscribe_receive([](std::string t) { std::cout << t; });

    bool landed = true;
    telemetry.subscribe_landed_state([&param, &landed, &mavlink, &mission, &mission_plan] (Telemetry::LandedState state)
    {
        if (state == Telemetry::LandedState::OnGround && !landed) {
            //parameter_change(param, 2);
        }
        landed = state == Telemetry::LandedState::OnGround;
    });

    bool armed = false;
    telemetry.subscribe_armed([&param, &mission, &armed] (bool state)
    {
        if (armed && !state) {
            //parameter_change(param, 4);
        }
        armed = state;
    });

    shell.send("gps stop");
    shell.send("fake_gps start");

    //param.get_all_params();

    std::atomic_bool should_exit{false};
    std::thread param_thread([&param, &should_exit]()
    {
        while (!should_exit.load(std::memory_order_relaxed))
        {
            sleep_for(milliseconds(100));
            //parameter_change(param, 0);
            sleep_for(milliseconds(100));
            //parameter_change(param, 1);
        }
    });

    std::thread mavlink_fire_thread([&mavlink]()
    {
        while (true)
        {
            for (int i = 0; i < 50; ++i)
            {
                MavlinkPassthrough::CommandLong cmd{0};
                cmd.command = 512;
                cmd.target_compid = 1;
                cmd.target_sysid = 1;
                cmd.param1 = 261;

                //mavlink.send_command_long(cmd);
                sleep_for(milliseconds(10));
            }
            sleep_for(milliseconds(1234));
        }
    });

    mission.upload_mission(mission_plan);
    sleep_for(seconds(3));

    for (int i = 0; i < 500; ++i)
    {
        std::cout << "#################### " << i << std::endl;

        //parameter_change(param, 0);
        //mission.set_current_mission_item(1);
        sleep_for(milliseconds(1000));
        //mission.start_mission();

        sleep_for(seconds(2));
        // Arm vehicle
        std::cout << "Arming...\n";
        const Action::Result arm_result = action.arm();

        if (arm_result != Action::Result::Success)
        {
            std::cerr << "Arming failed: " << arm_result << '\n';
            continue;
        }

        // Let it hover for a bit before landing again.
        sleep_for(seconds(1));

        std::cout << "Landing...\n";
        const Action::Result land_result = action.land();

        while (telemetry.in_air())
        {
            std::cout << "Vehicle is in air...\n";
            sleep_for(milliseconds(250));
        }
        //mission.upload_mission(mission_plan);
        sleep_for(milliseconds(650));
        parameter_change(param, 5);
        sleep_for(milliseconds(10));
        parameter_change(param, 6);
        sleep_for(milliseconds(10));
        parameter_change(param, 3);

        while (telemetry.armed())
        {
            std::cout << "Vehicle is armed...\n";
            sleep_for(milliseconds(250));
        }
        std::cout << "Disarmed!\n";
        // shell.send("top once");

        // We are relying on auto-disarming but let's keep watching the telemetry for a bit longer.
        sleep_for(seconds(3));
    }
    should_exit.store(true, std::memory_order_relaxed);
    param_thread.join();
    std::cout << "Finished...\n";

    return 0;
}
