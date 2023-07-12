# Copyright (C) 2017 - 2021 Dave Marples <dave@marples.net>
# SPDX-License-Identifier: BSD-3-Clause
# Copied from https://github.com/orbcode/orbuculum/blob/main/Support/gdbtrace.init

# ====================================================================
define orbuculum
  help orbuculum
end
document orbuculum
GDB SWO Trace Configuration Helpers
===================================

Setup Device
------------
STM32;
  enableSTM32SWO  : Enable SWO on STM32 pins (for F4 or F7 if 4/7 is passed as first argument)
  enableSTM32TRACE: Start TRACE on STM32 pins

IMXRT;
  enableIMXRT102XSWO : Enable SWO on IMXRT102X series pins (AD_B0_04)
  enableIMXRT106XSWO : Enable SWO on IMXRT106X series pins (AD_B0_10)

SAM5X;
  enableSAMD5XSWD    : Enable SWO on SAM5X output pin on SAM5X

NRF;
  enableNRF52TRACE : Start TRACE on NRF52 (not nrf52833 or nrf52840) pins
  enableNRF53TRACE : Start TRACE on NRF53* pins

EFR32MG12;
  enableEFR32MG12SWO : Start SWO on EFR32MG12 pins

All;
  prepareSWO      : Prepare SWO output in specified format
  startETM        : Start ETM output on channel 2

Configure DWT
-------------
dwtPOSTCNT        : Enable POSTCNT underflow event counter packet generation
dwtFOLDEVT        : Enable folded-instruction counter overflow event packet generation
dwtLSUEVT         : Enable LSU counter overflow event packet generation
dwtSLEEPEVT       : Enable Sleep counter overflow event packet generation
dwtDEVEVT         : Enable Exception counter overflow event packet generation
dwtCPIEVT         : Enable CPI counter overflow event packet generation
dwtTraceException : Enable Exception Trace Event packet generation
dwtSamplePC       : Enable PC sample using POSTCNT interval
dwtSyncTap        : Set how often Sync packets are sent out (None, CYCCNT[24], CYCCNT[26] or CYCCNT[28])
dwtPostTap        : Sets the POSTCNT tap (CYCCNT[6] or CYCCNT[10])
dwtPostInit       : Sets the initial value for the POSTCNT counter
dwtPostReset      : Sets the reload value for the POSTCNT counter
dwtCycEna         : Enable or disable CYCCNT

Configure ITM
-------------
ITMId             : Set the ITM ID for this device
ITMGTSFreq        : Set Global Timestamp frequency
ITMTSPrescale     : Set Timestamp Prescale
ITMSWOEna         : TS counter uses Processor Clock, or clock from TPIU Interface
ITMTXEna          : Control if DWT packets are forwarded to the ITM
ITMSYNCEna        : Control if sync packets are transmitted
ITMTSEna          : Enable local timestamp generation
ITMEna            : Master Enable for ITM
ITMTER            : Set Trace Enable Register bitmap for 32*<Block>
ITMTPR            : Enable block 8*bit access from unprivledged code

Configure ETM
-------------
describeETM       : Provide information about the ETM implementation on this target

end
# ====================================================================
# ====================================================================
# ====================================================================


# Definitions for the CPU types we currently support
set $CPU_IMXRT102X=1
set $CPU_STM32=2
set $CPU_IMXRT106X=1
set $CPU_NRF=3
set $CPU_EFR32=4

# ====================================================================
set $CDBBASE=0xE000EDF0
set $DWTBASE=0xE0001000
set $ITMBASE=0xE0000000
set $TPIUBASE=0xE0040000
set $ETMBASE=0xE0041000

define _setAddressesSTM32

# Locations in the memory map for interesting things on STM32
end

define _setAddressesIMXRT
# Locations in the memory map for interesting things on IMXRT
end

define _setAddressesNRF
# Locations in the memory map for interesting things on NRF
end

define _setAddressesNRF52
_setAddressesNRF
set $NRF_P0_PIN_CNF=0x50000700
set $NRF_CLOCK=0x40000000
end

define _setAddressesNRF53
_setAddressesNRF
set $CTIBASE=0xE0042000
set $SCSBASE=0xE000E000
set $BPUBASE=0xE0002000
set $NRF_TAD_S=0xE0080000
set $NRF_P0_S=0x50842500
set $NRF_SPU_S=0x50003000
end

define _setAddressesEFR32MG12
# Locations in the memory map for interesting things on EFR32
end

# ====================================================================

define startETM
  set $br_out=0
  if $argc >= 1
    set $br_out=$arg0
  end

  set $stall = 0
  if $argc >= 2
    set $stall = $arg1
  end

  # Allow access to device
  set *($ETMBASE+0xfb0) = 0xc5acce55

  # Enter configuration mode (write twice to be sure we reached it)
  set *($ETMBASE) = (1<<10)
  set *($ETMBASE) = (1<<10)

  # Set busID 2
  set *($ETMBASE+0x200) = 2

  # Set trigger event
  set *($ETMBASE+8) = 0x406f

  # Set to always enable in ETM Trace Enable Event
  set *($ETMBASE+0x20) = 0x6f

  # Trace and stall always enabled
  set *($ETMBASE+0x24) = 0x020000001

  # Stall when < 8 byes free in fifo
  set *($ETMBASE+0x2c) = 8

  # Enable trace
  set *($ETMBASE) = 0x0800 | ($stall << 7) | ($br_out << 8)

  # Essential that this bit is only cleared after everything else is done
  set *($ETMBASE) &= ~(1<<10)

end
document startETM
startETM <br_out> <stall>
<br_out>     : 1 = Explicitly report branch events
<stall>      : 1 = Stall the CPU when trace buffer is full
end

# ====================================================================
define describeETM
set $etmval = *($ETMBASE+0x1e4)
output ((($etmval>>8)&0x0f)+1)
echo .
output (($etmval>>4)&0x0f)
echo Rev
output (($etmval)&0x0f)
echo \n
if (((($etmval)>>24)&0xff)==0x41)
   echo Implementer is ARM\n
end
if (((($etmval)>>24)&0xff)==0x44)
echo Implementer is DEC\n
end
if (((($etmval)>>24)&0xff)==0x4D)
echo Implementer is Motorola/Freescale/NXP\n
end
if (((($etmval)>>24)&0xff)==0x51)
echo Implementer is Qualcomm\n
end
if (((($etmval)>>24)&0xff)==0x56)
echo Implementer is Marvell\n
end
if (((($etmval)>>24)&0xff)==0x69)
echo Implementer is Intel\n
end

if ($etmval&(1<<18))
   echo 32-bit Thumb instruction is traced as single instruction\n
   else
      echo 32-bit Thumb instruction is traced as two instructions\n
end
if ($etmval&(1<<19))
   echo Implements ARM architecture security extensions\n
   else
   echo No ARM architecture security extensions\n
end
if ($etmval&(1<<20))
   echo Uses alternative Branch Packet Encoding\n
   else
      echo Uses original Branch Packet Encoding\n
end
end

document describeETM
Provide information about the ETM implementation on this target.
end

# ====================================================================

define stopETM
  set *($ETMBASE) |= 0x400
end
document stopETM
stopETM
end

# ====================================================================

define prepareSWO
  set $clockspeed=72000000
  set $speed=2250000
  set $useTPIU=0
  set $useMan=0

  if $argc >= 1
    set $clockspeed = $arg0
  end

  if $argc >= 2
    set $speed = $arg1
  end

  if $argc >= 3
    set $useTPIU = $arg2
  end

  if $argc >= 4
    set $useMan = $arg3
  end

  # Make sure we can get to everything
  set *($ITMBASE+0xfb0) = 0xc5acce55
  set *($ETMBASE+0xfb0) = 0xc5acce55

  set *($CDBBASE+0xC)|=(1<<24)

  if ($useMan==0)
    # Use Async mode pin protocol (TPIU_SPPR)
    set *($TPIUBASE+0xF0) = 2
  else
    # Use Manchester mode pin protocol (TPIU_SPPR)
    set *($TPIUBASE+0xF0) = 1

    # There are two edges in a bit, so double the clock
    set $speed = $speed*2
  end

  # Output bits at speed dependent on system clock
  set *($TPIUBASE+0x10) = ((($clockspeed+$speed-1)/$speed)-1)

  if ($useTPIU==1)
    # Use TPIU formatter and flush
    set *($TPIUBASE+0x304) = 0x102
  else
    set *($TPIUBASE+0x304) = 0x100
  end

  # Flush all initial configuration
  set *($CDBBASE+0xC)|=(1<<24)
  set *($DWTBASE) = 0
  set *($ITMBASE+0xe80) = 0
end
document prepareSWO
prepareSWO <ClockSpd> <Speed> <UseTPIU> <UseMan>: Prepare output trace data port at specified speed
  <ClockSpd>: Speed of the CPU SystemCoreClock
  <Speed>   : Speed to use (Ideally an integer divisor of SystemCoreClock)
  <UseTPIU> : Set to 1 to use TPIU
  <UseMan>  : Set to 1 use use Manchester encoding
end

# ====================================================================
define enableIMXRT102XSWO

  _setAddressesIMXRT
  # Store the CPU we are using
  set $CPU=$CPU_IMXRT102X

  # Set AD_B0_04 to be an input, and no drive (defaults to JTAG otherwise)
  set *0x401f80cc=5
  set *0x401f8240=0

  # Set AD_B0_11 to be SWO, with specific output characteristics
  set *0x401F80E8=6
  set *0x401F825C=0x6020
end
document enableIMXRT102XSWO
enableIMXRT102XSWO Configure output pin on IMXRT102X for SWO use.
end

define enableIMXRT1021SWO
       enableIMXRT102XSWO
end
# ====================================================================
define enableIMXRT106XSWO
  _setAddressesIMXRT
  # Store the CPU we are using
  set $CPU=$CPU_IMXRT106X

  # Disable Trace Clocks while we change them (CCM_CCGR0)
#  set *0x400FC068&=~(3<<22)
    set *0x400FC068|=(3<<22)

  # Set Trace clock input to be from PLL2 PFD2 (CBCMR1, 396 MHz)
  set *0x400Fc018&=~(3<<14)
  set *0x400Fc018|=(1<<14)

  # Set divider to be 3 (CSCDR1, 132 MHz)
  set *0x400Fc024&=~(3<<25)
  set *0x400Fc024|=(2<<25)

  # Enable Trace Clocks (CCGR0)
  set *0x400FC068|=(3<<22)

  # Set AD_B0_10 to be SWO, with specific output characteristics (MUX_CTL & PAD_CTL)
  set *0x401F80E4=9
  set *0x401F82D4=0xB0A1
end
document enableIMXRT106XSWO
enableIMXRT1021SWO Configure output pin on IMXRT1060 for SWO use.
end
# ====================================================================

define enableSTM32SWO
  set $tgt=1
  if $argc >= 1
    set $tgt = $arg0
  end

  set $CPU=$CPU_STM32
   _setAddressesSTM32
  if (($tgt==4) || ($tgt==7))
    # STM32F4/7 variant.
    # Enable AHB1ENR
    set *0x40023830 |= 0x02
    # Set MODER for PB3
    set *0x40020400 &= ~(0x000000C0)
    set *0x40020400 |= 0x00000080
    # Set max (100MHz) speed in OSPEEDR
    set *0x40020408 |= 0x000000C0
    # No pull up or down in PUPDR
    set *0x4002040C &= ~(0x000000C0)
    # Set AF0 (==TRACESWO) in AFRL
    set *0x40020420 &= ~(0x0000F000)
  else
    # STM32F1 variant.
    # RCC->APB2ENR |= RCC_APB2ENR_AFIOEN;
    set *0x40021018 |= 1
    # AFIO->MAPR |= (2 << 24); // Disable JTAG to release TRACESWO
    set *0x40010004 |= 0x2000000
  end
  # Common initialisation.
  # DBGMCU->CR |= DBGMCU_CR_TRACE_IOEN;
  set *0xE0042004 |= 0x20
end
document enableSTM32SWO
enableSTM32SWO Configure output pin on STM32 for SWO use.
end
# ====================================================================
define enableSAMD5XSWD
  # Enable peripheral channel clock on GCLK#0
  # GCLK->PHCTRL[47] = GCLK_PCHCTRL_GEN(0)
  set *(unsigned char *)0x40001D3C = 0
  # GCLK->PHCTRL[47] |= GCLK_PCHCTRL_CHEN
  set *(unsigned char *)0x40001D3C |= 0x40
  # Configure PINMUX for GPIOB.30. '7' is SWO.
  set *(unsigned char *)0x410080BF |= 0x07
  set *(unsigned char *)0x410080DE = 0x01
end
document enableSAMD5XSWD
enableSAMD5XSWD Configure output pin on SAM5X for SWO use.
end

# ====================================================================
define enableEFR32MG12SWO

  _setAddressesEFR32MG12
  # Store the CPU we are using
  set $CPU=$CPU_EFR32

  # Enable the GPIO clock (HFBUSCLKEN0)
  # CMU->HFBUSCLKEN0 |= CMU_HFBUSCLKEN0_GPIO
  set *0x400E40B0 |= (1<<3)

  # Enable Trace Clocks (CMU_OSCENCMD_AUXHFRCOEN)
  # CMU->OSCENCMD = CMU_OSCENCMD_AUXHFRCOEN
  set *0x400E4060 = (1<<4)

  # Enable SWO Output
  # GPIO->ROUTEPEN |= GPIO_ROUTEPEN_SWVPEN
  set *0x4000A440 |= (1<<4)

  # Route SWO to correct pin (GPIO->ROUTELOC0=0/_GPIO_ROUTELOC0_SWVLOC_MASK=3/BSP_TRACE_SWO_LOCATION=0)
  # GPIO->ROUTELOC0 = (GPIO->ROUTELOC0 & ~(_GPIO_ROUTELOC0_SWVLOC_MASK)) | BSP_TRACE_SWO_LOCATION
  set *0x4000A444 = 0

  # Configure GPIO Port F, Pin 2 for output
  # GPIO->P[5].MODEL &= ~(_GPIO_P_MODEL_MODE2_MASK);
  # GPIO->P[5].MODEL |= GPIO_P_MODEL_MODE2_PUSHPULL;
  set *0x4000A0F4 &= ~(0xF00)
  set *0x4000A0F4 |= (4 << 8)
end
document enableEFR32MG12SWO
enableEFR32MG12SWO Configure output pin on EFR32MG12 for SWO use.
end


# ====================================================================
# Enable CORTEX TRACE on preconfigured pins
define _doTRACE
     # Must be called with $bits containing number of bits to set trace for

     set *($ITMBASE+0xfb0) = 0xc5acce55
     set *($ETMBASE+0xfb0) = 0xc5acce55
     set *($TPIUBASE+0xfb0) = 0xc5acce55

     # Set port size (TPIU_CSPSR)
     set *($TPIUBASE+4) = (1<<$bits)

     # Set pin protocol to Sync Trace Port (TPIU_SPPR)
     set *($TPIUBASE+0xF0)=0
end
# ====================================================================
define enableSTM32TRACE
  set $bits=4
  set $drive=1

  if $argc >= 1
    set $bits = $arg0
  end
    if (($bits<1) || ($bits==3) || ($bits>4))
    help enableSTM32TRACE
  end

  if $argc >= 2
    set $drive = $arg1
  end

print $drive
  if ($drive > 3)
    help enableSTM32TRACE
  end

  set $bits = $bits-1
  set $CPU=$CPU_STM32

  _setAddressesSTM32
  # Enable AHB1ENR
  set *0x40023830 |= 0x10

  # Enable compensation cell
  set *0x40023844 |= (1<<14)
  set *0x40013820 |=1

  # Setup PE2 & PE3
  # Port Mode
  set *0x40021000 &= ~(0x000000F0)
  set *0x40021000 |= 0xA0

  # Drive speed
  set *0x40021008 &= ~0xf0
  set *0x40021008 |= ($drive<<4)|($drive<<6)

  # No Pull up or down
  set *0x4002100C &= ~0xF0
  # AF0
  set *0x40021020 &= ~0xF0

  if ($bits>0)
     # Setup PE4
     set *0x40021000 &= ~(0x00000300)
     set *0x40021000 |= 0x200
     set *0x40021008 &= ~0x300
     set *0x40021008 |= ($drive<<8)
     set *0x4002100C &= ~0x300
     set *0x40021020 &= ~0x300
  end

  if ($bits>1)
     # Setup PE5 & PE6

     set *0x40021000 &= ~(0x00003C00)
     set *0x40021000 |= 0x2800
     set *0x40021008 &= ~0x3C00
     set *0x40021008 |= ($drive<<10)|($drive<<12)
     set *0x4002100C &= ~0x3C00
     set *0x40021020 &= ~0x3C00
  end

  # Set number of bits in DBGMCU_CR
  set *0xE0042004 &= ~(3<<6)

  if ($bits<3)
     set *0xE0042004 |= ((($bits+1)<<6) | (1<<5))
  else
     set *0xE0042004 |= ((3<<6) | (1<<5))
  end

  # Enable Trace TRCENA (DCB DEMCR)
  set *($CDBBASE+0xC)=(1<<24)

  # Finally start the trace output
  _doTRACE
end
document enableSTM32TRACE
enableSTM32TRACE <Width>: Enable TRACE on STM32 pins
  <Width>   : Number of bits wide (1,2 or 4 only)
  <Drive>   : Drive strength (0=lowest, 3=highest)
end
# ====================================================================
define enableNRF52TRACE
  set $bits=4
  set $cspeed=1
  set $drive=3

  if $argc >= 1
    set $bits = $arg0
  end
    if (($bits<1) || ($bits==3) || ($bits>4))
    help enableNRF53TRACE
  end

  if $argc >= 2
    set $drive=$arg1
  end
  if (($drive!=0) & ($drive!=3))
     help enableNRF52TRACE
  end

  if $argc >= 3
    set $cspeed=$arg2
  end
  if (( $cspeed < 0 ) || ( $cspeed > 3))
    help enableNRF52TRACE
  end

  set $bits = $bits-1
  set $CPU=$CPU_NRF

  _setAddressesNRF52

  # from modules/nrfx/mdk/system_nrf52.c
  # CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  set *($CDBBASE+0xC) |= (1<<24)

  # NRF_CLOCK->TRACECONFIG |= CLOCK_TRACECONFIG_TRACEMUX_Parallel << CLOCK_TRACECONFIG_TRACEMUX_Pos;
  set *($NRF_CLOCK+0x0000055C) &= ~(3 << 16)
  set *($NRF_CLOCK+0x0000055C) |= (2 << 16)
  set *($NRF_CLOCK+0x0000055C) &= ~(3 << 0)
  set *($NRF_CLOCK+0x0000055C) |= ($cspeed << 0)

  if ($bits>0)
    # NRF_P0->PIN_CNF[18] = (GPIO_PIN_CNF_DRIVE_H0H1 << GPIO_PIN_CNF_DRIVE_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) | (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos);
    set *($NRF_P0_PIN_CNF+18*4) = (($drive<<8) | (0<<1) | (1<<0))
    # NRF_P0->PIN_CNF[20] = (GPIO_PIN_CNF_DRIVE_H0H1 << GPIO_PIN_CNF_DRIVE_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) | (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos);
    set *($NRF_P0_PIN_CNF+20*4) = (($drive<<8) | (0<<1) | (1<<0))
    if ($bits>1)
      # NRF_P0->PIN_CNF[14] = (GPIO_PIN_CNF_DRIVE_H0H1 << GPIO_PIN_CNF_DRIVE_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) | (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos);
      set *($NRF_P0_PIN_CNF+14*4) = (($drive<<8) | (0<<1) | (1<<0))
      # NRF_P0->PIN_CNF[15] = (GPIO_PIN_CNF_DRIVE_H0H1 << GPIO_PIN_CNF_DRIVE_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) | (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos);
      set *($NRF_P0_PIN_CNF+15*4) = (($drive<<8) | (0<<1) | (1<<0))
      # NRF_P0->PIN_CNF[16] = (GPIO_PIN_CNF_DRIVE_H0H1 << GPIO_PIN_CNF_DRIVE_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) | (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos);
      set *($NRF_P0_PIN_CNF+16*4) = (($drive<<8) | (0<<1) | (1<<0))
    end
  end
  # Finally start the trace output
  _doTRACE
end
document enableNRF52TRACE
enableNRF52TRACE <Drive> <Speed> : Enable TRACE on NRF52 pins (not nrf52833 or nrf52840)
  <Width>   : Number of bits wide (1,2 or 4 only)
  <Drive>   : Drive strength (0 (low), 3 (high))
  <Speed>   : Clock Speed (0..3, 0 fastest)
end
# ====================================================================
define enableNRF53TRACE
  set $bits=4
  set $cspeed=1
  set $drive=11
  #11

  if $argc >= 1
    set $bits = $arg0
  end
    if (($bits<1) || ($bits==3) || ($bits>4))
    help enableNRF53TRACE
  end

  if $argc >= 2
    set $drive=$arg1
  end

  if ((($drive<0) || ($drive>3)) && ($drive!=11))
     help enableNRF53TRACE
  end

  if $argc >= 3
    set $cspeed=$arg2
  end
  if (( $cspeed < 0 ) || ( $cspeed > 3))
    help enableNRF53TRACE
  end

  set $bits = $bits-1
  set $CPU=$CPU_NRF

  _setAddressesNRF53
  # Actions from Section 8.9 of the manual
  # NRF_TAD_S->ENABLE = TAD_ENABLE_ENABLE_Msk
  set *($NRF_TAD_S+0x500) = 1

  # NRF_TAD_S->CLOCKSTART = TAD_CLOCKSTART_START_Msk
  set *($NRF_TAD_S+4) = 1

  # Release permissions ( NRF_SPU_S->GPIOPORT[0].PERM )
  # Set pins to be controlled
  # NRF_TAD_S->PSEL.TRACECLK = TAD_PSEL_TRACECLK_PIN_Traceclk
  # NRF_TAD_S->PSEL.TRACEDATAX = TAD_PSEL_TRACEDATA0_PIN_TracedataX

  set *($NRF_SPU_S+0x4c0 ) &=~ ( (1<<12)|(1<<11) )

  set *($NRF_TAD_S+0x504+0) = 12
  set *($NRF_TAD_S+0x504+4) = 11
  set *($NRF_P0_S + 0x200 + 4*12  ) = (7<<28) | ( $drive << 8)
  set *($NRF_P0_S + 0x200 + 4*11  ) = (7<<28) | ( $drive << 8)

  if ($bits>0)
    set *($NRF_SPU_S+0x4c0 ) &=~ ( 1<<10 )

    set *($NRF_TAD_S+0x504+8) = 10
    set *($NRF_P0_S + 0x200 + 4*10  ) = (7<<28) | ( $drive << 8)

    if ($bits>1)
      set *($NRF_SPU_S+0x4c0 ) &=~ ( (1<<9)|(1<<8) )
      set *($NRF_TAD_S+0x504+0x0C) = 9
      set *($NRF_TAD_S+0x504+0x10) = 8
      set *($NRF_P0_S + 0x200 + 4*9  ) = (7<<28) | ( $drive << 8)
      set *($NRF_P0_S + 0x200 + 4*8  ) = (7<<28) | ( $drive << 8)
    end
  end


  # NRF_TAD_S->TRACEPORTSPEED = TAD_TRACEPORTSPEED_TRACEPORTSPEED_64MHz
  # Can be 0..3
  set *($NRF_TAD_S+0x518) = $cspeed

  # Enable Trace TRCENA (DCB DEMCR)
  set *($CDBBASE+0xC)=(1<<24)

  # Finally start the trace output
  _doTRACE
end
document enableNRF53TRACE
enableNRF53TRACE <Width> <drive> <speed> : Enable TRACE on NRF pins
  <Width>   : Number of bits wide (1,2 or 4 only)
  <Drive>   : Drive strength (0 (lowest), 1, 2, 3 or 11 (highest))
  <Speed>   : Clock Speed (0..3, 0 fastest)
end
# ====================================================================
define dwtPOSTCNT
  if ($argc!=1)
    help dwtPOSTCNT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<22)
    else
      set *($DWTBASE) &= ~(1<<22)
    end
  end
end
document dwtPOSTCNT
dwtPOSTCNT <0|1> Enable POSTCNT underflow event counter packet generation
end
# ====================================================================
define dwtFOLDEVT
  if ($argc!=1)
    help dwtFOLDEVT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<21)
    else
      set *($DWTBASE) &= ~(1<<21)
    end
  end
end
document dwtFOLDEVT
dwtFOLDEVT <0|1> Enable folded-instruction counter overflow event packet generation
end
# ====================================================================
define dwtLSUEVT
  if ($argc!=1)
    help dwtLSUEVT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<20)
    else
      set *($DWTBASE) &= ~(1<<20)
    end
  end
end
document dwtLSUEVT
dwtLSUEVT <0|1> Enable LSU counter overflow event packet generation
end
# ====================================================================
define dwtSLEEPEVT
  if ($argc!=1)
    help dwtSLEEPEVT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<19)
    else
      set *($DWTBASE) &= ~(1<<19)
    end
  end
end
document dwtSLEEPEVT
dwtSLEEPEVT <0|1> Enable Sleep counter overflow event packet generation
end
# ====================================================================
define dwtDEVEVT
  if ($argc!=1)
    help dwtCEVEVT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<18)
    else
      set *($DWTBASE) &= ~(1<<18)
    end
  end
end
document dwtDEVEVT
dwtDEVEVT <0|1> Enable Exception counter overflow event packet generation
end
# ====================================================================
define dwtCPIEVT
  if ($argc!=1)
    help dwtCPIEVT
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<17)
    else
      set *($DWTBASE) &= ~(1<<17)
    end
  end
end
document dwtCPIEVT
dwtCPIEVT <0|1> Enable CPI counter overflow event packet generation
end
# ====================================================================
define dwtTraceException
  if ($argc!=1)
    help dwtTraceException
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<16)
    else
      set *($DWTBASE) &= ~(1<<16)
    end
  end
end
document dwtTraceException
dwtTraceException <0|1> Enable Exception Trace Event packet generation
end
# ====================================================================
define dwtSamplePC
  if ($argc!=1)
    help dwtSamplePC
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<12)
    else
      set *($DWTBASE) &= ~(1<<12)
    end
  end
end
document dwtSamplePC
dwtSamplePC <0|1> Enable PC sample using POSTCNT interval
end
# ====================================================================
define dwtSyncTap
  if (($argc!=1) || ($arg0<0) || ($arg0>3))
    help dwtSyncTap
  else
    set *($CDBBASE|0xC) |= 0x1000000
    set *($DWTBASE) &= ~(0x03<<10)
    set *($DWTBASE) |= (($arg0&0x03)<<10)
  end
end
document dwtSyncTap
dwtSyncTap <0..3> Set how often Sync packets are sent out (None, CYCCNT[24], CYCCNT[26] or CYCCNT[28])
end
# ====================================================================
define dwtPostTap
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help dwtPostTap
  else
    set *($CDBBASE|0xC) |= 0x1000000
    if ($arg0==0)
      set *($DWTBASE) &= ~(1<<9)
    else
      set *($DWTBASE) |= (1<<9)
    end
  end
end
document dwtPostTap
dwtPostTap <0..1> Sets the POSTCNT tap (CYCCNT[6] or CYCCNT[10])
end
# ====================================================================
define dwtPostInit
  if (($argc!=1) || ($arg0<0) || ($arg0>15))
    help dwtPostInit
  else
    set *($CDBBASE+0xC) |= 0x1000000
    set *($DWTBASE) &= ~(0x0f<<5)
    set *($DWTBASE) |= (($arg0&0x0f)<<5)
  end
end
document dwtPostInit
dwtPostInit <0..15> Sets the initial value for the POSTCNT counter
end
# ====================================================================
define dwtPostReset
  if (($argc!=1) || ($arg0<0) || ($arg0>15))
    help dwtPostReset
  else
    set *($CDBBASE+0xC) |= 0x1000000
    set *($DWTBASE) &= ~(0x0f<<1)
    set *($DWTBASE) |= (($arg0&0x0f)<<1)
  end
end
document dwtPostReset
dwtPostReset <0..15> Sets the reload value for the POSTCNT counter
In conjunction with the dwtPostTap, this gives you a relatively wide range
of sampling speeds.  Lower numbers are faster.
end
# ====================================================================
define dwtCycEna
  if ($argc!=1)
    help dwtCycEna
  else
    set *($CDBBASE+0xC) |= 0x1000000
    if ($arg0==1)
      set *($DWTBASE) |= (1<<0)
    else
      set *($DWTBASE) &= ~(1<<0)
    end
  end
end
document dwtCycEna
dwtCycEna <0|1> Enable or disable CYCCNT
end
# ====================================================================
# ====================================================================
define ITMId
  if (($argc!=1) || ($arg0<0) || ($arg0>127))
    help ITMBusId
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    set *($ITMBASE+0xe80) &= ~(0x7F<<16)
    set *($ITMBASE+0xe80) |= (($arg0&0x7f)<<16)
  end
end
document ITMId
ITMId <0..127>: Set the ITM ID for this device
end
# ====================================================================
define ITMGTSFreq
  if (($argc!=1) || ($arg0<0) || ($arg0>3))
    help ITMGTSFreq
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    set *($ITMBASE+0xe80) &= ~(0x3<<10)
    set *($ITMBASE+0xe80) |= (($arg0&3)<<10)
  end
end
document ITMGTSFreq
ITMGTSFreq <0..3> Set Global Timestamp frequency
          [0-Disable, 1-Approx 128 Cycles,
           2-Approx 8192 Cycles, 3-Whenever possible]
end
# ====================================================================
define ITMTSPrescale
  if (($argc!=1) || ($arg0<0) || ($arg0>3))
    help ITMGTSFreq
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    set *($ITMBASE+0xe80) &= ~(0x3<<8)
    set *($ITMBASE+0xe80) |= (($arg0&3)<<8)
  end
end
document ITMTSPrescale
ITMTSPrescale <0..3> Set Timestamp Prescale [0-No Prescale, 1-/4, 2-/16, 3-/64
end
# ====================================================================
define ITMSWOEna
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help ITMSWOEna
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    if ($arg0==0)
      set *($ITMBASE+0xe80) &= ~(0x1<<4)
    else
      set *($ITMBASE+0xe80) |= (($arg0&1)<<4)
    end
  end
end
document ITMSWOEna
ITMSWOEna <0|1> 0-TS counter uses Processor Clock
                1-TS counter uses clock from TPIU Interface, and is held in reset while the output line is idle.
end
# ====================================================================
define ITMTXEna
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help ITMTXEna
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    if ($arg0==0)
      set *($ITMBASE+0xe80) &= ~(0x1<<3)
    else
      set *($ITMBASE+0xe80) |= (($arg0&1)<<3)
    end
  end
end
document ITMTXEna
ITMTXEna <0|1> 0-DWT packets are not forwarded to the ITM
               1-DWT packets are output to the ITM
end
# ====================================================================
define ITMSYNCEna
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help ITMSYNCEna
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    if ($arg0==0)
      set *($ITMBASE+0xe80) &= ~(0x1<<2)
    else
      set *($ITMBASE+0xe80) |= (($arg0&1)<<2)
    end
  end
end
document ITMSYNCEna
ITMSYNCEna <0|1> 0-Sync packets are not transmitted
                 1-Sync paclets are transmitted
end
# ====================================================================
define ITMTSEna
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help ITMTSEna
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    if ($arg0==0)
      set *($ITMBASE+0xe80) &= ~(0x1<<1)
    else
      set *($ITMBASE+0xe80) |= (($arg0&1)<<1)
    end
  end
end
document ITMTSEna
ITMTSEna <0|1> Enable local timestamp generation
end
# ====================================================================
define ITMEna
  if (($argc!=1) || ($arg0<0) || ($arg0>1))
    help ITMEna
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    if ($arg0==0)
      set *($ITMBASE+0xe80) &= ~(0x1<<0)
    else
      set *($ITMBASE+0xe80) |= (($arg0&1)<<0)
    end
  end
end
document ITMEna
ITMEna <0|1> Master Enable for ITM
end
# ====================================================================
define ITMTER
  if (($argc!=2) || ($arg0<0) || ($arg0>7))
    help ITMTER
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    set *($ITMBASE+0xe00+4*$arg0) = $arg1
  end
end
document ITMTER
ITMTER <Block> <Bitmask> Set Trace Enable Register bitmap for 32*<Block>
end
# ====================================================================
define ITMTPR
  if ($argc!=1)
    help ITMTPR
  else
    set *($ITMBASE+0xfb0) = 0xc5acce55
    set *($ITMBASE+0xe40) = $arg0
  end
end
document ITMTPR
ITMTPR <Bitmask> Enable block 8*bit access from unprivledged code
end
# ====================================================================
