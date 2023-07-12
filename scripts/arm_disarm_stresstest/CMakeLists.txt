# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.10.2)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

project(arm_disarm_stresstest)

add_executable(arm_disarm_stresstest
    main.cpp
)

find_package(MAVSDK REQUIRED)
find_package(Threads REQUIRED)

target_link_libraries(arm_disarm_stresstest
    MAVSDK::mavsdk
    Threads::Threads
)

if(NOT MSVC)
    add_compile_options(arm_disarm_stresstest PRIVATE -Wall -Wextra)
else()
    add_compile_options(arm_disarm_stresstest PRIVATE -WX -W2)
endif()
