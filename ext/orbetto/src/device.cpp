// Copyright (c) 2024, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#include "device.hpp"
using namespace std::literals;

static const Device::IrqTable irq_names_stm32f765 =
{
    {16+-14, "NonMaskableInt"},     // 2 Non Maskable Interrupt
    {16+-13, "HardFault"},          // 3 Cortex-M Hard Fault Interrupt
    {16+-12, "MemoryManagement"},   // 4 Cortex-M Memory Management Interrupt
    {16+-11, "BusFault"},           // 5 Cortex-M Bus Fault Interrupt
    {16+-10, "UsageFault"},         // 6 Cortex-M Usage Fault Interrupt
    {16+ -5, "SVCall"},             // 11 Cortex-M SV Call Interrupt
    {16+ -4, "DebugMonitor"},       // 12 Cortex-M Debug Monitor Interrupt
    {16+ -2, "PendSV"},             // 14 Cortex-M Pend SV Interrupt
    {16+ -1, "SysTick"},            // 15 Cortex-M System Tick Interrupt

    {16+  0, "WWDG"},               // Window WatchDog Interrupt
    {16+  1, "PVD"},                // PVD through EXTI Line detection Interrupt
    {16+  2, "TAMP_STAMP"},         // Tamper and TimeStamp interrupts through the EXTI line
    {16+  3, "RTC_WKUP"},           // RTC Wakeup interrupt through the EXTI line
    {16+  4, "FLASH"},              // FLASH global Interrupt
    {16+  5, "RCC"},                // RCC global Interrupt
    {16+  6, "EXTI0"},              // EXTI Line0 Interrupt
    {16+  7, "EXTI1"},              // EXTI Line1 Interrupt
    {16+  8, "EXTI2"},              // EXTI Line2 Interrupt
    {16+  9, "EXTI3"},              // EXTI Line3 Interrupt
    {16+ 10, "EXTI4"},              // EXTI Line4 Interrupt
    {16+ 11, "DMA1_Stream0"},       // DMA1 Stream 0 global Interrupt
    {16+ 12, "DMA1_Stream1"},       // DMA1 Stream 1 global Interrupt
    {16+ 13, "DMA1_Stream2"},       // DMA1 Stream 2 global Interrupt
    {16+ 14, "DMA1_Stream3"},       // DMA1 Stream 3 global Interrupt
    {16+ 15, "DMA1_Stream4"},       // DMA1 Stream 4 global Interrupt
    {16+ 16, "DMA1_Stream5"},       // DMA1 Stream 5 global Interrupt
    {16+ 17, "DMA1_Stream6"},       // DMA1 Stream 6 global Interrupt
    {16+ 18, "ADC"},                // ADC1, ADC2 and ADC3 global Interrupts
    {16+ 19, "CAN1_TX"},            // CAN1 TX Interrupt
    {16+ 20, "CAN1_RX0"},           // CAN1 RX0 Interrupt
    {16+ 21, "CAN1_RX1"},           // CAN1 RX1 Interrupt
    {16+ 22, "CAN1_SCE"},           // CAN1 SCE Interrupt
    {16+ 23, "EXTI9_5"},            // External Line[9:5] Interrupts
    {16+ 24, "TIM1_BRK_TIM9"},      // TIM1 Break interrupt and TIM9 global interrupt
    {16+ 25, "TIM1_UP_TIM10"},      // TIM1 Update Interrupt and TIM10 global interrupt
    {16+ 26, "TIM1_TRG_COM_TIM11"}, // TIM1 Trigger and Commutation Interrupt and TIM11 global interrupt
    {16+ 27, "TIM1_CC"},            // TIM1 Capture Compare Interrupt
    {16+ 28, "TIM2"},               // TIM2 global Interrupt
    {16+ 29, "TIM3"},               // TIM3 global Interrupt
    {16+ 30, "TIM4"},               // TIM4 global Interrupt
    {16+ 31, "I2C1_EV"},            // I2C1 Event Interrupt
    {16+ 32, "I2C1_ER"},            // I2C1 Error Interrupt
    {16+ 33, "I2C2_EV"},            // I2C2 Event Interrupt
    {16+ 34, "I2C2_ER"},            // I2C2 Error Interrupt
    {16+ 35, "SPI1"},               // SPI1 global Interrupt
    {16+ 36, "SPI2"},               // SPI2 global Interrupt
    {16+ 37, "USART1"},             // USART1 global Interrupt
    {16+ 38, "USART2"},             // USART2 global Interrupt
    {16+ 39, "USART3"},             // USART3 global Interrupt
    {16+ 40, "EXTI15_10"},          // External Line[15:10] Interrupts
    {16+ 41, "RTC_Alarm"},          // RTC Alarm (A and B) through EXTI Line Interrupt
    {16+ 42, "OTG_FS_WKUP"},        // USB OTG FS Wakeup through EXTI line interrupt
    {16+ 43, "TIM8_BRK_TIM12"},     // TIM8 Break Interrupt and TIM12 global interrupt
    {16+ 44, "TIM8_UP_TIM13"},      // TIM8 Update Interrupt and TIM13 global interrupt
    {16+ 45, "TIM8_TRG_COM_TIM14"}, // TIM8 Trigger and Commutation Interrupt and TIM14 global interrupt
    {16+ 46, "TIM8_CC"},            // TIM8 Capture Compare Interrupt
    {16+ 47, "DMA1_Stream7"},       // DMA1 Stream7 Interrupt
    {16+ 48, "FMC"},                // FMC global Interrupt
    {16+ 49, "SDMMC1"},             // SDMMC1 global Interrupt
    {16+ 50, "TIM5"},               // TIM5 global Interrupt
    {16+ 51, "SPI3"},               // SPI3 global Interrupt
    {16+ 52, "UART4"},              // UART4 global Interrupt
    {16+ 53, "UART5"},              // UART5 global Interrupt
    {16+ 54, "TIM6_DAC"},           // TIM6 global and DAC1&2 underrun error  interrupts
    {16+ 55, "TIM7"},               // TIM7 global interrupt
    {16+ 56, "DMA2_Stream0"},       // DMA2 Stream 0 global Interrupt
    {16+ 57, "DMA2_Stream1"},       // DMA2 Stream 1 global Interrupt
    {16+ 58, "DMA2_Stream2"},       // DMA2 Stream 2 global Interrupt
    {16+ 59, "DMA2_Stream3"},       // DMA2 Stream 3 global Interrupt
    {16+ 60, "DMA2_Stream4"},       // DMA2 Stream 4 global Interrupt
    {16+ 61, "ETH"},                // Ethernet global Interrupt
    {16+ 62, "ETH_WKUP"},           // Ethernet Wakeup through EXTI line Interrupt
    {16+ 63, "CAN2_TX"},            // CAN2 TX Interrupt
    {16+ 64, "CAN2_RX0"},           // CAN2 RX0 Interrupt
    {16+ 65, "CAN2_RX1"},           // CAN2 RX1 Interrupt
    {16+ 66, "CAN2_SCE"},           // CAN2 SCE Interrupt
    {16+ 67, "OTG_FS"},             // USB OTG FS global Interrupt
    {16+ 68, "DMA2_Stream5"},       // DMA2 Stream 5 global interrupt
    {16+ 69, "DMA2_Stream6"},       // DMA2 Stream 6 global interrupt
    {16+ 70, "DMA2_Stream7"},       // DMA2 Stream 7 global interrupt
    {16+ 71, "USART6"},             // USART6 global interrupt
    {16+ 72, "I2C3_EV"},            // I2C3 event interrupt
    {16+ 73, "I2C3_ER"},            // I2C3 error interrupt
    {16+ 74, "OTG_HS_EP1_OUT"},     // USB OTG HS End Point 1 Out global interrupt
    {16+ 75, "OTG_HS_EP1_IN"},      // USB OTG HS End Point 1 In global interrupt
    {16+ 76, "OTG_HS_WKUP"},        // USB OTG HS Wakeup through EXTI interrupt
    {16+ 77, "OTG_HS"},             // USB OTG HS global interrupt
    {16+ 78, "DCMI"},               // DCMI global interrupt
    {16+ 80, "RNG"},                // RNG global interrupt
    {16+ 81, "FPU"},                // FPU global interrupt
    {16+ 82, "UART7"},              // UART7 global interrupt
    {16+ 83, "UART8"},              // UART8 global interrupt
    {16+ 84, "SPI4"},               // SPI4 global Interrupt
    {16+ 85, "SPI5"},               // SPI5 global Interrupt
    {16+ 86, "SPI6"},               // SPI6 global Interrupt
    {16+ 87, "SAI1"},               // SAI1 global Interrupt
    {16+ 90, "DMA2D"},              // DMA2D global Interrupt
    {16+ 91, "SAI2"},               // SAI2 global Interrupt
    {16+ 92, "QUADSPI"},            // Quad SPI global interrupt
    {16+ 93, "LPTIM1"},             // LP TIM1 interrupt
    {16+ 94, "CEC"},                // HDMI-CEC global Interrupt
    {16+ 95, "I2C4_EV"},            // I2C4 Event Interrupt
    {16+ 96, "I2C4_ER"},            // I2C4 Error Interrupt
    {16+ 97, "SPDIF_RX"},           // SPDIF-RX global Interrupt
    {16+ 99, "DFSDM1_FLT0"},        // DFSDM1 Filter 0 global Interrupt
    {16+100, "DFSDM1_FLT1"},        // DFSDM1 Filter 1 global Interrupt
    {16+101, "DFSDM1_FLT2"},        // DFSDM1 Filter 2 global Interrupt
    {16+102, "DFSDM1_FLT3"},        // DFSDM1 Filter 3 global Interrupt
    {16+103, "SDMMC2"},             // SDMMC2 global Interrupt
    {16+104, "CAN3_TX"},            // CAN3 TX Interrupt
    {16+105, "CAN3_RX0"},           // CAN3 RX0 Interrupt
    {16+106, "CAN3_RX1"},           // CAN3 RX1 Interrupt
    {16+107, "CAN3_SCE"},           // CAN3 SCE Interrupt
    {16+109, "MDIOS"},              // MDIO Slave global Interrupt
};


static const Device::IrqTable irq_names_stm32h753 =
{
    {16+-14, "NonMaskableInt"},     // 2 Non Maskable Interrupt
    {16+-13, "HardFault"},          // 3 Cortex-M Hard Fault Interrupt
    {16+-12, "MemoryManagement"},   // 4 Cortex-M Memory Management Interrupt
    {16+-11, "BusFault"},           // 5 Cortex-M Bus Fault Interrupt
    {16+-10, "UsageFault"},         // 6 Cortex-M Usage Fault Interrupt
    {16+ -5, "SVCall"},             // 11 Cortex-M SV Call Interrupt
    {16+ -4, "DebugMonitor"},       // 12 Cortex-M Debug Monitor Interrupt
    {16+ -2, "PendSV"},             // 14 Cortex-M Pend SV Interrupt
    {16+ -1, "SysTick"},            // 15 Cortex-M System Tick Interrupt

    {16+  0, "WWDG"},               // Window WatchDog Interrupt ( wwdg1_it, wwdg2_it)
    {16+  1, "PVD_AVD"},            // PVD/AVD through EXTI Line detection Interrupt
    {16+  2, "TAMP_STAMP"},         // Tamper and TimeStamp interrupts through the EXTI line
    {16+  3, "RTC_WKUP"},           // RTC Wakeup interrupt through the EXTI line
    {16+  4, "FLASH"},              // FLASH global Interrupt
    {16+  5, "RCC"},                // RCC global Interrupt
    {16+  6, "EXTI0"},              // EXTI Line0 Interrupt
    {16+  7, "EXTI1"},              // EXTI Line1 Interrupt
    {16+  8, "EXTI2"},              // EXTI Line2 Interrupt
    {16+  9, "EXTI3"},              // EXTI Line3 Interrupt
    {16+ 10, "EXTI4"},              // EXTI Line4 Interrupt
    {16+ 11, "DMA1_Stream0"},       // DMA1 Stream 0 global Interrupt
    {16+ 12, "DMA1_Stream1"},       // DMA1 Stream 1 global Interrupt
    {16+ 13, "DMA1_Stream2"},       // DMA1 Stream 2 global Interrupt
    {16+ 14, "DMA1_Stream3"},       // DMA1 Stream 3 global Interrupt
    {16+ 15, "DMA1_Stream4"},       // DMA1 Stream 4 global Interrupt
    {16+ 16, "DMA1_Stream5"},       // DMA1 Stream 5 global Interrupt
    {16+ 17, "DMA1_Stream6"},       // DMA1 Stream 6 global Interrupt
    {16+ 18, "ADC"},                // ADC1 and  ADC2 global Interrupts
    {16+ 19, "FDCAN1_IT0"},         // FDCAN1 Interrupt line 0
    {16+ 20, "FDCAN2_IT0"},         // FDCAN2 Interrupt line 0
    {16+ 21, "FDCAN1_IT1"},         // FDCAN1 Interrupt line 1
    {16+ 22, "FDCAN2_IT1"},         // FDCAN2 Interrupt line 1
    {16+ 23, "EXTI9_5"},            // External Line[9:5] Interrupts
    {16+ 24, "TIM1_BRK"},           // TIM1 Break Interrupt
    {16+ 25, "TIM1_UP"},            // TIM1 Update Interrupt
    {16+ 26, "TIM1_TRG_COM"},       // TIM1 Trigger and Commutation Interrupt
    {16+ 27, "TIM1_CC"},            // TIM1 Capture Compare Interrupt
    {16+ 28, "TIM2"},               // TIM2 global Interrupt
    {16+ 29, "TIM3"},               // TIM3 global Interrupt
    {16+ 30, "TIM4"},               // TIM4 global Interrupt
    {16+ 31, "I2C1_EV"},            // I2C1 Event Interrupt
    {16+ 32, "I2C1_ER"},            // I2C1 Error Interrupt
    {16+ 33, "I2C2_EV"},            // I2C2 Event Interrupt
    {16+ 34, "I2C2_ER"},            // I2C2 Error Interrupt
    {16+ 35, "SPI1"},               // SPI1 global Interrupt
    {16+ 36, "SPI2"},               // SPI2 global Interrupt
    {16+ 37, "USART1"},             // USART1 global Interrupt
    {16+ 38, "USART2"},             // USART2 global Interrupt
    {16+ 39, "USART3"},             // USART3 global Interrupt
    {16+ 40, "EXTI15_10"},          // External Line[15:10] Interrupts
    {16+ 41, "RTC_Alarm"},          // RTC Alarm (A and B) through EXTI Line Interrupt
    {16+ 43, "TIM8_BRK_TIM12"},     // TIM8 Break Interrupt and TIM12 global interrupt
    {16+ 44, "TIM8_UP_TIM13"},      // TIM8 Update Interrupt and TIM13 global interrupt
    {16+ 45, "TIM8_TRG_COM_TIM14"}, // TIM8 Trigger and Commutation Interrupt and TIM14 global interrupt
    {16+ 46, "TIM8_CC"},            // TIM8 Capture Compare Interrupt
    {16+ 47, "DMA1_Stream7"},       // DMA1 Stream7 Interrupt
    {16+ 48, "FMC"},                // FMC global Interrupt
    {16+ 49, "SDMMC1"},             // SDMMC1 global Interrupt
    {16+ 50, "TIM5"},               // TIM5 global Interrupt
    {16+ 51, "SPI3"},               // SPI3 global Interrupt
    {16+ 52, "UART4"},              // UART4 global Interrupt
    {16+ 53, "UART5"},              // UART5 global Interrupt
    {16+ 54, "TIM6_DAC"},           // TIM6 global and DAC1&2 underrun error  interrupts
    {16+ 55, "TIM7"},               // TIM7 global interrupt
    {16+ 56, "DMA2_Stream0"},       //   DMA2 Stream 0 global Interrupt
    {16+ 57, "DMA2_Stream1"},       //   DMA2 Stream 1 global Interrupt
    {16+ 58, "DMA2_Stream2"},       //   DMA2 Stream 2 global Interrupt
    {16+ 59, "DMA2_Stream3"},       //   DMA2 Stream 3 global Interrupt
    {16+ 60, "DMA2_Stream4"},       //   DMA2 Stream 4 global Interrupt
    {16+ 61, "ETH"},                // Ethernet global Interrupt
    {16+ 62, "ETH_WKUP"},           // Ethernet Wakeup through EXTI line Interrupt
    {16+ 63, "FDCAN_CAL"},          // FDCAN Calibration unit Interrupt
    {16+ 68, "DMA2_Stream5"},       // DMA2 Stream 5 global interrupt
    {16+ 69, "DMA2_Stream6"},       // DMA2 Stream 6 global interrupt
    {16+ 70, "DMA2_Stream7"},       // DMA2 Stream 7 global interrupt
    {16+ 71, "USART6"},             // USART6 global interrupt
    {16+ 72, "I2C3_EV"},            // I2C3 event interrupt
    {16+ 73, "I2C3_ER"},            // I2C3 error interrupt
    {16+ 74, "OTG_HS_EP1_OUT"},     // USB OTG HS End Point 1 Out global interrupt
    {16+ 75, "OTG_HS_EP1_IN"},      // USB OTG HS End Point 1 In global interrupt
    {16+ 76, "OTG_HS_WKUP"},        // USB OTG HS Wakeup through EXTI interrupt
    {16+ 77, "OTG_HS"},             // USB OTG HS global interrupt
    {16+ 78, "DCMI"},               // DCMI global interrupt
    {16+ 79, "CRYP"},               // CRYP crypto global interrupt
    {16+ 80, "HASH_RNG"},           // HASH and RNG global interrupt
    {16+ 81, "FPU"},                // FPU global interrupt
    {16+ 82, "UART7"},              // UART7 global interrupt
    {16+ 83, "UART8"},              // UART8 global interrupt
    {16+ 84, "SPI4"},               // SPI4 global Interrupt
    {16+ 85, "SPI5"},               // SPI5 global Interrupt
    {16+ 86, "SPI6"},               // SPI6 global Interrupt
    {16+ 87, "SAI1"},               // SAI1 global Interrupt
    {16+ 88, "LTDC"},               // LTDC global Interrupt
    {16+ 89, "LTDC_ER"},            // LTDC Error global Interrupt
    {16+ 90, "DMA2D"},              // DMA2D global Interrupt
    {16+ 91, "SAI2"},               // SAI2 global Interrupt
    {16+ 92, "QUADSPI"},            // Quad SPI global interrupt
    {16+ 93, "LPTIM1"},             // LP TIM1 interrupt
    {16+ 94, "CEC"},                // HDMI-CEC global Interrupt
    {16+ 95, "I2C4_EV"},            // I2C4 Event Interrupt
    {16+ 96, "I2C4_ER"},            // I2C4 Error Interrupt
    {16+ 97, "SPDIF_RX"},           // SPDIF-RX global Interrupt
    {16+ 98, "OTG_FS_EP1_OUT"},     // USB OTG HS2 global interrupt
    {16+ 99, "OTG_FS_EP1_IN"},      // USB OTG HS2 End Point 1 Out global interrupt
    {16+100, "OTG_FS_WKUP"},        // USB OTG HS2 End Point 1 In global interrupt
    {16+101, "OTG_FS"},             // USB OTG HS2 Wakeup through EXTI interrupt
    {16+102, "DMAMUX1_OVR"},        // Overrun interrupt
    {16+103, "HRTIM1_Master"},      // HRTIM Master Timer global Interrupts
    {16+104, "HRTIM1_TIMA"},        // HRTIM Timer A global Interrupt
    {16+105, "HRTIM1_TIMB"},        // HRTIM Timer B global Interrupt
    {16+106, "HRTIM1_TIMC"},        // HRTIM Timer C global Interrupt
    {16+107, "HRTIM1_TIMD"},        // HRTIM Timer D global Interrupt
    {16+108, "HRTIM1_TIME"},        // HRTIM Timer E global Interrupt
    {16+109, "HRTIM1_FLT"},         // HRTIM Fault global Interrupt
    {16+110, "DFSDM1_FLT0"},        // Filter1 Interrupt
    {16+111, "DFSDM1_FLT1"},        // Filter2 Interrupt
    {16+112, "DFSDM1_FLT2"},        // Filter3 Interrupt
    {16+113, "DFSDM1_FLT3"},        // Filter4 Interrupt
    {16+114, "SAI3"},               // SAI3 global Interrupt
    {16+115, "SWPMI1"},             // Serial Wire Interface 1 global interrupt
    {16+116, "TIM15"},              // TIM15 global Interrupt
    {16+117, "TIM16"},              // TIM16 global Interrupt
    {16+118, "TIM17"},              // TIM17 global Interrupt
    {16+119, "MDIOS_WKUP"},         // MDIOS Wakeup  Interrupt
    {16+120, "MDIOS"},              // MDIOS global Interrupt
    {16+121, "JPEG"},               // JPEG global Interrupt
    {16+122, "MDMA"},               // MDMA global Interrupt
    {16+124, "SDMMC2"},             // SDMMC2 global Interrupt
    {16+125, "HSEM1"},              // HSEM1 global Interrupt
    {16+127, "ADC3"},               // ADC3 global Interrupt
    {16+128, "DMAMUX2_OVR"},        // Overrun interrupt
    {16+129, "BDMA_Channel0"},      // BDMA Channel 0 global Interrupt
    {16+130, "BDMA_Channel1"},      // BDMA Channel 1 global Interrupt
    {16+131, "BDMA_Channel2"},      // BDMA Channel 2 global Interrupt
    {16+132, "BDMA_Channel3"},      // BDMA Channel 3 global Interrupt
    {16+133, "BDMA_Channel4"},      // BDMA Channel 4 global Interrupt
    {16+134, "BDMA_Channel5"},      // BDMA Channel 5 global Interrupt
    {16+135, "BDMA_Channel6"},      // BDMA Channel 6 global Interrupt
    {16+136, "BDMA_Channel7"},      // BDMA Channel 7 global Interrupt
    {16+137, "COMP"},               // COMP global Interrupt
    {16+138, "LPTIM2"},             // LP TIM2 global interrupt
    {16+139, "LPTIM3"},             // LP TIM3 global interrupt
    {16+140, "LPTIM4"},             // LP TIM4 global interrupt
    {16+141, "LPTIM5"},             // LP TIM5 global interrupt
    {16+142, "LPUART1"},            // LP UART1 interrupt
    {16+144, "CRS"},                // Clock Recovery Global Interrupt
    {16+145, "ECC"},                // ECC diagnostic Global Interrupt
    {16+146, "SAI4"},               // SAI4 global interrupt
    {16+149, "WAKEUP_PIN"},         // Interrupt for all 6 wake-up pins
};

static const Device::RegisterTable registers_stm32h753 =
{
    {0x40003820, "SPI2.TXDR"},
    {0x40003830, "SPI2.RXDR"},
    {0x40003c20, "SPI3.TXDR"},
    {0x40003c30, "SPI3.RXDR"},
    {0x40004824, "USART3.RDR"},
    {0x40004828, "USART3.TDR"},
    {0x40005024, "UART5.RDR"},
    {0x40005028, "UART5.TDR"},
    {0x40007824, "UART7.RDR"},
    {0x40007828, "UART7.TDR"},
    {0x40011424, "USART1.RDR"},
    {0x40011428, "USART1.TDR"},
    {0x40013020, "SPI1.TXDR"},
    {0x40013030, "SPI1.RXDR"},
};


Device::Device(std::string_view hint)
{
    // hint.contains() is only available in C++23
    if (hint.find("stm32f765") != std::string_view::npos or
        hint.find("v5x") != std::string_view::npos)
    {
        _irq_table = &irq_names_stm32f765;
        // FIXME
        // _register_table = &registers_stm32f765;
        _max_irq = 16+109;
        _clock = 216'000'000;
        _id = DeviceId::SYKNODE_V5X;
    }
    else if (hint.find("stm32h753") != std::string_view::npos or
             hint.find("v6x") != std::string_view::npos)
    {
        _irq_table = &irq_names_stm32h753;
        _register_table = &registers_stm32h753;
        _max_irq = 16+149;
        _clock = 480'000'000;
        _id = DeviceId::SYKNODE_V6X;
    }
    // this was used in a pure NuttX build as ETM test
    else if (hint.find("nuttx") != std::string_view::npos)
    {
        _irq_table = &irq_names_stm32f765;
        _max_irq = 16+109;
        _clock = 48'000'000;
        _id = DeviceId::SYKNODE_V5X;
    }
}
