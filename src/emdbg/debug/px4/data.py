# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

_fmu_v5x = {
    "A0":  ("ADC1_IN0", "SCALED_VDD_3V3_SENSORS1"),
    "A1":  ("ETH_REF_CLK", "ETH_REF_CLK"),
    "A2":  ("ETH_MDIO", "ETH_MDIO"),
    "A3":  ("USART2_RX", "USART2_RX_TELEM3"),
    "A4":  ("ADC1_IN4", "SCALED_VDD_3V3_SENSORS2"),
    "A5":  ("SPI1_SCK", "SPI1_SCK_SENSOR1_ICM20602"),
    "A6":  ("SPI6_MISO", "SPI6_MISO_EXTERNAL1"),
    "A7":  ("ETH_CRS_DV", "ETH_CRS_DV"),
    "A8":  ("TIM1_CH1", "FMU_CH4"),
    "A9":  ("USB_OTG_FS_VBUS", "VBUS_SENSE"),
    "A10": ("TIM1_CH3", "FMU_CH2"),
    "A11": ("USB_OTG_FS_DM", "USB_D_N"),
    "A12": ("USB_OTG_FS_DP", "USB_D_P"),
    "A13": ("SWDIO", "FMU_SWDIO"),
    "A14": ("SWCLK", "FMU_SWCLK"),
    "A15": ("", "SPI6_nCS2_EXTERNAL1"),
    "B0":  ("ADC1_IN8", "SCALED_VDD_3V3_SENSORS3"),
    "B1":  ("ADC1_IN9", "SCALED_V5"),
    "B2":  ("SPI3_MOSI", "SPI3_MOSI_SENSOR3_BMI088"),
    "B3":  ("SPI6_SCK", "SPI6_SCK_EXTERNAL1"),
    "B4":  ("SPI1_MISO", "SPI1_MISO_SENSOR1_ICM20602"),
    "B5":  ("SPI1_MOSI", "SPI1_MOSI_SENSOR1_ICM20602"),
    "B6":  ("CAN2_TX", "CAN2_TX"),
    "B7":  ("I2C1_SDA", "I2C1_SDA_BASE_GPS1_MAG_LED_PM1"),
    "B8":  ("I2C1_SCL", "I2C1_SCL_BASE_GPS1_MAG_LED_PM1"),
    "B9":  ("UART5_TX", "UART5_TX_TELEM2"),
    "B10": ("TIM2_CH3", "HEATER"),
    "B11": ("ETH_TX_EN", "ETH_TX_EN"),
    "B12": ("CAN2_RX", "CAN2_RX"),
    "B13": ("ETH_TXD1", "ETH_TXD1"),
    "B14": ("USART1_TX", "USART1_TX_GPS1"),
    "B15": ("USART1_RX", "USART1_RX_GPS1"),
    "C0":  ("ADC1_IN10", "ADC1_6V6"),
    "C1":  ("ETH_MDC", "ETH_MDC"),
    "C2":  ("ADC1_IN12", "SCALED_VDD_3V3_SENSORS4"),
    "C3":  ("ADC1_IN13", "ADC1_3V3"),
    "C4":  ("ETH_RXD0", "ETH_RXD0"),
    "C5":  ("ETH_RXD1", "ETH_RXD1"),
    "C6":  ("USART6_TX", "USART6_TX_TO_IO__NC"),
    "C7":  ("USART6_RX", "USART6_RX_FROM_IO__RC_INPUT"),
    "C8":  ("UART5_RTS", "UART5_RTS_TELEM2"),
    "C9":  ("UART5_CTS", "UART5_CTS_TELEM2"),
    "C10": ("SPI3_SCK", "SPI3_SCK_SENSOR3_BMI088"),
    "C11": ("SPI3_MISO", "SPI3_MISO_SENSOR3_BMI088"),
    "C12": ("", "nARMED"),
    "C13": ("", "VDD_3V3_SD_CARD_EN"),
    "C14": ("OSC32_IN", "32KHZ_IN"),
    "C15": ("OSC32_OUT", "32KHZ_OUT"),
    "D0":  ("CAN1_RX", "CAN1_RX"),
    "D1":  ("CAN1_TX", "CAN1_TX"),
    "D2":  ("UART5_RX", "UART5_RX_TELEM2"),
    "D3":  ("USART2_CTS", "USART2_CTS_TELEM3"),
    "D4":  ("USART2_RTS", "USART2_RTS_TELEM3"),
    "D5":  ("USART2_TX", "USART2_TX_TELEM3"),
    "D6":  ("SDMMC2_CLK", "SDMMC2_CLK"),
    "D7":  ("SDMMC2_CMD", "SDMMC2_CMD"),
    "D8":  ("USART3_TX", "USART3_TX_DEBUG"),
    "D9":  ("USART3_RX", "USART3_RX_DEBUG"),
    "D10": ("", "FMU_nSAFETY_SWITCH_LED_OUT"),
    "D11": ("", "SPI6_DRDY1_EXTERNAL1"),
    "D12": ("", "SPI6_DRDY2_EXTERNAL1"),
    "D13": ("TIM4_CH2", "FMU_CH5"),
    "D14": ("TIM4_CH3", "FMU_CH6"),
    "D15": ("", "VDD_3V3_SENSORS2_EN"),
    "E0":  ("UART8_RX", "UART8_RX_GPS2"),
    "E1":  ("UART8_TX", "UART8_TX_GPS2"),
    "E2":  ("", "TRACECLK"),
    "E3":  ("", "nLED_RED"),
    "E4":  ("", "nLED_GREEN"),
    "E5":  ("", "nLED_BLUE"),
    "E6":  ("SPI4_MOSI", "SPI4_MOSI_SENSOR4_BMM150"),
    "E7":  ("", "VDD_3V3_SENSORS3_EN"),
    "E8":  ("UART7_TX", "UART7_TX_TELEM1"),
    "E9":  ("UART7_RTS", "UART7_RTS_TELEM1"),
    "E10": ("UART7_CTS", "UART7_CTS_TELEM1"),
    "E11": ("TIM1_CH2", "FMU_CH3"),
    "E12": ("SPI4_SCK", "SPI4_SCK_SENSOR4_BMM150"),
    "E13": ("SPI4_MISO", "SPI4_MISO_SENSOR4_BMM150"),
    "E14": ("TIM1_CH4", "FMU_CH1"),
    "E15": ("", "VDD_5V_PERIPH_nOC"),
    "F0":  ("I2C2_SDA", "I2C2_SDA_BASE_GPS2_MAG_LED_PM2"),
    "F1":  ("I2C2_SCL", "I2C2_SCL_BASE_GPS2_MAG_LED_PM2"),
    "F2":  ("", "SPI1_DRDY1_ICM20602"),
    "F3":  ("", "SPI4_DRDY1_BMM150_DRDY"),
    "F4":  ("ADC3_IN14", "HW_VER_SENSE"),
    "F5":  ("ADC3_IN15", "HW_REV_SENSE"),
    "F6":  ("UART7_RX", "UART7_RX_TELEM1"),
    "F7":  ("SPI5_SCK", "SPI5_SCK_FRAM"),
    "F8":  ("SPI5_MISO", "SPI5_MISO_FRAM"),
    "F9":  ("TIM14_CH1", "BUZZER_1"),
    "F10": ("", "SPI6_nRESET_EXTERNAL1"),
    "F11": ("SPI5_MOSI", "SPI5_MOSI_FRAM"),
    "F12": ("", "VDD_5V_HIPOWER_nEN"),
    "F13": ("", "VDD_5V_HIPOWER_nOC"),
    "F14": ("I2C4_SCL", "I2C4_SCL_FMU"),
    "F15": ("I2C4_SDA", "I2C4_SDA_FMU"),
    "G0":  ("", "HW_VER_REV_DRIVE"),
    "G1":  ("", "nPOWER_IN_A"),
    "G2":  ("", "nPOWER_IN_B"),
    "G3":  ("", "nPOWER_IN_C"),
    "G4":  ("", "VDD_5V_PERIPH_nEN"),
    "G5":  ("", "I2C2_DRDY1_BMP388"),
    # "G6":  ("", ""),
    "G7":  ("", "SPI5_nCS1_FRAM"),
    "G8":  ("", "VDD_3V3_SENSORS4_EN"),
    "G9":  ("SDMMC2_D0", "SDMMC2_D0"),
    "G10": ("SDMMC2_D1", "SDMMC2_D1"),
    "G11": ("SDMMC2_D2", "SDMMC2_D2"),
    "G12": ("SDMMC2_D3", "SDMMC2_D3"),
    "G13": ("ETH_TXD0", "ETH_TXD0"),
    "G14": ("SPI6_MOSI", "SPI6_MOSI_EXTERNAL1"),
    "G15": ("", "ETH_POWER_EN"),
    "H0":  ("OSC_IN", "16_MHZ_IN"),
    "H1":  ("OSC_OUT", "16_MHZ_OUT"),
    "H2":  ("", "VDD_3V3_SPEKTRUM_POWER_EN"),
    "H3":  ("", "NFC_GPIO"),
    "H4":  ("", "FMU_SAFETY_SWITCH_IN"),
    "H5":  ("", "SPI2_nCS1_ISM330"),
    "H6":  ("TIM12_CH1", "FMU_CH7"),
    "H7":  ("I2C3_SCL", "I2C3_SCL_BASE_MS5611_BARBED_EXTERNAL1"),
    "H8":  ("I2C3_SDA", "I2C3_SDA_BASE_MS5611_BARBED_EXTERNAL1"),
    "H9":  ("TIM12_CH2", "FMU_CH8"),
    "H10": ("TIM5_CH1", "SPIX_SYNC"),
    # "H11": ("", ""),
    "H12": ("TIM5_CH3", "SPI2_DRDY2_ISM330_INT2"),
    "H13": ("UART4_TX", "UART4_TX"),
    "H14": ("UART4_RX", "UART4_RX"),
    "H15": ("", "SPI4_nCS1_BMM150"),
    "I0":  ("TIM5_CH4", "FMU_CAP1"),
    "I1":  ("SPI2_SCK", "SPI2_SCK_SENSOR2_ISM330"),
    "I2":  ("SPI2_MISO", "SPI2_MISO_SENSOR2_ISM330"),
    "I3":  ("SPI2_MOSI", "SPI2_MOSI_SENSOR2_ISM330"),
    "I4":  ("", "SPI3_nCS1_BMI088_ACCEL"),
    "I5":  ("TIM8_CH1_IN", "FMU_PPM_INPUT"),
    "I6":  ("", "SPI3_DRDY1_BMI088_INT1_ACCEL"),
    "I7":  ("", "SPI3_DRDY2_BMI088_INT3_GYRO"),
    "I8":  ("", "SPI3_nCS2_BMI088_GYRO"),
    "I9":  ("", "SPI1_nCS1_ICM20602"),
    "I10": ("", "SPI6_nCS1_EXTERNAL1"),
    "I11": ("", "VDD_3V3_SENSORS1_EN"),
}

_fmu_v6x = {
    "A0":  ("ADC1_IN0", "SCALED_VDD_3V3_SENSORS1"),
    "A1":  ("ETH_REF_CLK", "ETH_REF_CLK"),
    "A2":  ("ETH_MDIO", "ETH_MDIO"),
    "A3":  ("USART2_RX", "USART2_RX_TELEM3"),
    "A4":  ("ADC1_IN4", "SCALED_VDD_3V3_SENSORS2"),
    "A5":  ("SPI1_SCK", "SPI1_SCK_SENSOR1_ICM20602"),
    "A6":  ("SPI6_MISO", "SPI6_MISO_EXTERNAL1"),
    "A7":  ("ETH_CRS_DV", "ETH_CRS_DV"),
    "A8":  ("TIM1_CH1", "FMU_CH4"),
    "A9":  ("USB_OTG_FS_VBUS", "VBUS_SENSE"),
    "A10": ("TIM1_CH3", "FMU_CH2"),
    "A11": ("USB_OTG_FS_DM", "USB_D_N"),
    "A12": ("USB_OTG_FS_DP", "USB_D_P"),
    "A13": ("SWDIO", "FMU_SWDIO"),
    "A14": ("SWCLK", "FMU_SWCLK"),
    "A15": ("PA15", "SPI6_nCS2_EXTERNAL1"),
    "B0":  ("ADC1_IN8", "SCALED_VDD_3V3_SENSORS3"),
    "B1":  ("ADC1_IN9", "SCALED_V5"),
    "B2":  ("SPI3_MOSI", "SPI3_MOSI_SENSOR3_BMI088"),
    "B3":  ("SPI6_SCK", "SPI6_SCK_EXTERNAL1"),
    "B4":  ("SPI1_MISO", "SPI1_MISO_SENSOR1_ICM20602"),
    "B5":  ("SPI1_MOSI", "SPI1_MOSI_SENSOR1_ICM20602"),
    "B6":  ("CAN2_TX", "CAN2_TX"),
    "B7":  ("I2C1_SDA", "I2C1_SDA_BASE_GPS1_MAG_LED_PM1"),
    "B8":  ("I2C1_SCL", "I2C1_SCL_BASE_GPS1_MAG_LED_PM1"),
    "B9":  ("UART5_TX", "UART5_TX_TELEM2"),
    "B10": ("TIM2_CH3", "HEATER"),
    "B11": ("ETH_TX_EN", "ETH_TX_EN"),
    "B12": ("CAN2_RX", "CAN2_RX"),
    "B13": ("ETH_TXD1", "ETH_TXD1"),
    "B14": ("USART1_TX", "USART1_TX_GPS1"),
    "B15": ("USART1_RX", "USART1_RX_GPS1"),
    "C0":  ("ADC1_IN10", "ADC1_6V6"),
    "C1":  ("ETH_MDC", "ETH_MDC"),
    "C2":  ("ADC1_IN12", "SCALED_VDD_3V3_SENSORS4"),
    "C3":  ("ADC1_IN13", "ADC1_3V3"),
    "C4":  ("ETH_RXD0", "ETH_RXD0"),
    "C5":  ("ETH_RXD1", "ETH_RXD1"),
    "C6":  ("USART6_TX", "USART6_TX_TO_IO__NC"),
    "C7":  ("USART6_RX", "USART6_RX_FROM_IO__RC_INPUT"),
    "C8":  ("UART5_RTS", "UART5_RTS_TELEM2"),
    "C9":  ("UART5_CTS", "UART5_CTS_TELEM2"),
    "C10": ("SPI3_SCK", "SPI3_SCK_SENSOR3_BMI088"),
    "C11": ("SPI3_MISO", "SPI3_MISO_SENSOR3_BMI088"),
    "C12": ("PC12", "nARMED"),
    "C13": ("PC13", "VDD_3V3_SD_CARD_EN"),
    "C14": ("OSC32_IN", "32KHZ_IN"),
    "C15": ("OSC32_OUT", "32KHZ_OUT"),
    "D0":  ("CAN1_RX", "CAN1_RX"),
    "D1":  ("CAN1_TX", "CAN1_TX"),
    "D2":  ("UART5_RX", "UART5_RX_TELEM2"),
    "D3":  ("USART2_CTS", "USART2_CTS_TELEM3"),
    "D4":  ("USART2_RTS", "USART2_RTS_TELEM3"),
    "D5":  ("USART2_TX", "USART2_TX_TELEM3"),
    "D6":  ("SDMMC2_CLK","SDMMC2_CLK"),
    "D7":  ("SDMMC2_CMD","SDMMC2_CMD"),
    "D8":  ("USART3_TX", "USART3_TX_DEBUG"),
    "D9":  ("USART3_RX", "USART3_RX_DEBUG"),
    "D10": ("PD10", "FMU_nSAFETY_SWITCH_LED_OUT"),
    "D11": ("PD11", "SPI6_DRDY1_EXTERNAL1"),
    "D12": ("PD12", "SPI6_DRDY2_EXTERNAL1"),
    "D13": ("TIM4_CH2", "FMU_CH5"),
    "D14": ("TIM4_CH3", "FMU_CH6"),
    "D15": ("PD15", "VDD_3V3_SENSORS2_EN"),
    "E0":  ("UART8_RX", "UART8_RX_GPS2"),
    "E1":  ("UART8_TX", "UART8_TX_GPS2"),
    "E2":  ("PE2", "TRACECLK"),
    "E3":  ("PE3", "nLED_RED"),
    "E4":  ("PE4", "nLED_GREEN"),
    "E5":  ("PE5", "nLED_BLUE"),
    "E6":  ("SPI4_MOSI", "SPI4_MOSI_SENSOR4_BMM150"),
    "E7":  ("PE7", "VDD_3V3_SENSORS3_EN"),
    "E8":  ("UART7_TX", "UART7_TX_TELEM1"),
    "E9":  ("UART7_RTS", "UART7_RTS_TELEM1"),
    "E10": ("UART7_CTS", "UART7_CTS_TELEM1"),
    "E11": ("TIM1_CH2", "FMU_CH3"),
    "E12": ("SPI4_SCK", "SPI4_SCK_SENSOR4_BMM150"),
    "E13": ("SPI4_MISO", "SPI4_MISO_SENSOR4_BMM150"),
    "E14": ("TIM1_CH4", "FMU_CH1"),
    "E15": ("PE15", "VDD_5V_PERIPH_nOC"),
    "F0":  ("I2C2_SDA", "I2C2_SDA_BASE_GPS2_MAG_LED_PM2"),
    "F1":  ("I2C2_SCL", "I2C2_SCL_BASE_GPS2_MAG_LED_PM2"),
    "F2":  ("PF2", "SPI1_DRDY1_ICM20602"),
    "F3":  ("PF3", "SPI4_DRDY1_BMM150_DRDY"),
    "F4":  ("ADC3_IN14", "HW_VER_SENSE"),
    "F5":  ("ADC3_IN15", "HW_REV_SENSE"),
    "F6":  ("UART7_RX", "UART7_RX_TELEM1"),
    "F7":  ("SPI5_SCK", "SPI5_SCK_FRAM"),
    "F8":  ("SPI5_MISO", "SPI5_MISO_FRAM"),
    "F9":  ("TIM14_CH1", "BUZZER_1"),
    "F10": ("PF10", "SPI6_nRESET_EXTERNAL1"),
    "F11": ("SPI5_MOSI", "SPI5_MOSI_FRAM"),
    "F12": ("PF12", "VDD_5V_HIPOWER_nEN"),
    "F13": ("PF13", "VDD_5V_HIPOWER_nOC"),
    "F14": ("I2C4_SCL", "I2C4_SCL_FMU"),
    "F15": ("I2C4_SDA", "I2C4_SDA_FMU"),
    "G0":  ("PG0", "HW_VER_REV_DRIVE"),
    "G1":  ("PG1", "nPOWER_IN_A"),
    "G2":  ("PG2", "nPOWER_IN_B"),
    "G3":  ("PG3", "nPOWER_IN_C"),
    "G4":  ("PG4", "VDD_5V_PERIPH_nEN"),
    "G5":  ("PG5", "I2C2_DRDY1_BMP388"),
    "G6":  ("PG6", "PG6"),
    "G7":  ("PG7", "SPI5_nCS1_FRAM"),
    "G8":  ("PG8", "VDD_3V3_SENSORS4_EN"),
    "G9":  ("SDMMC2_D0","SDMMC2_D0"),
    "G10": ("SDMMC2_D1","SDMMC2_D1"),
    "G11": ("SDMMC2_D2","SDMMC2_D2"),
    "G12": ("SDMMC2_D3","SDMMC2_D3"),
    "G13": ("ETH_TXD0", "ETH_TXD0"),
    "G14": ("SPI6_MOSI", "SPI6_MOSI_EXTERNAL1"),
    "G15": ("PG15", "ETH_POWER_EN"),
    "H0":  ("OSC_IN", "16_MHZ_IN"),
    "H1":  ("OSC_OUT", "16_MHZ_OUT"),
    "H2":  ("PH2", "VDD_3V3_SPEKTRUM_POWER_EN"),
    "H3":  ("PH3", "NFC_GPIO"),
    "H4":  ("PH4", "FMU_SAFETY_SWITCH_IN"),
    "H5":  ("PH5", "SPI2_nCS1_ISM330"),
    "H6":  ("TIM12_CH1", "FMU_CH7"),
    "H7":  ("I2C3_SCL", "I2C3_SCL_BASE_MS5611_BARBED_EXTERNAL1"),
    "H8":  ("I2C3_SDA", "I2C3_SDA_BASE_MS5611_BARBED_EXTERNAL1"),
    "H9":  ("TIM12_CH2", "FMU_CH8"),
    "H10": ("TIM5_CH1", "SPIX_SYNC"),
    "H11": ("PH11", "PH11"),
    "H12": ("TIM5_CH3", "SPI2_DRDY2_ISM330_INT2"),
    "H13": ("UART4_TX", "UART4_TX"),
    "H14": ("UART4_RX", "UART4_RX"),
    "H15": ("PH15", "SPI4_nCS1_BMM150"),
    "I0":  ("TIM5_CH4", "FMU_CAP1"),
    "I1":  ("SPI2_SCK", "SPI2_SCK_SENSOR2_ISM330"),
    "I2":  ("SPI2_MISO", "SPI2_MISO_SENSOR2_ISM330"),
    "I3":  ("SPI2_MOSI", "SPI2_MOSI_SENSOR2_ISM330"),
    "I4":  ("PI4", "SPI3_nCS1_BMI088_ACCEL"),
    "I5":  ("TIM8_CH1_IN", "FMU_PPM_INPUT"),
    "I6":  ("PI6", "SPI3_DRDY1_BMI088_INT1_ACCEL"),
    "I7":  ("PI7", "SPI3_DRDY2_BMI088_INT3_GYRO"),
    "I8":  ("PI8", "SPI3_nCS2_BMI088_GYRO"),
    "I9":  ("PI9", "SPI1_nCS1_ICM20602"),
    "I10": ("PI10", "SPI6_nCS1_EXTERNAL1"),
    "I11": ("PI11", "VDD_3V3_SENSORS1_EN"),
}

from .device import Device


def pinout(gdb, hint=None) -> dict:
    return {
        0x0451: _fmu_v5x,
        0x0450: _fmu_v6x,
    }.get(Device(gdb).devid, {})
