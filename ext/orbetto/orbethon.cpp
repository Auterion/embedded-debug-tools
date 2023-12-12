#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "orbetto.cpp"

namespace py = pybind11;

PYBIND11_MODULE(orbethon,handle){
    handle.doc()="Python rapper for orbetto tool.";
    handle.def("orbethon",&main_pywrapper);

    py::class_<PyOptions>(handle,"Options_Struct")
        /* Default class init for python */
        .def(py::init())
        /* Config information */
        //.def_readwrite("useTPIU",&Options::useTPIU)
        //.def_readwrite("tpiuChannel",&Options::tpiuChannel)
        //.def_readwrite("forceITMSync",&Options::forceITMSync)
        .def_readwrite("cps",&PyOptions::cps)
        .def_readwrite("tsType",&PyOptions::tsType)
        //.def_readwrite("tsLineFormat",&Options::tsLineFormat)
        //.def_readwrite("tsTrigger",&Options::tsTrigger)
        /* Sink information */
        // careful this is different from c++ implementation and has to be converted as pybind has no char*[]
        //.def_readwrite("presFormat",&Options::presFormat)
        /* Source information */
        //.def_readwrite("port",&Options::port)
        //.def_readwrite("server",&Options::server)
        .def_readwrite("std_file",&PyOptions::std_file)
        .def_readwrite("endTerminate",&PyOptions::endTerminate)
        .def_readwrite("elf_file",&PyOptions::elf_file)
        .def_readwrite("outputDebugFile",&PyOptions::outputDebugFile)
        .def_readwrite("functions",&PyOptions::functions)
        .def_readwrite("miso_digital",&PyOptions::miso_digital)
        .def_readwrite("mosi_digital",&PyOptions::mosi_digital)
        .def_readwrite("clk_digital",&PyOptions::clk_digital)
        .def_readwrite("cs_digital",&PyOptions::cs_digital)
        .def_readwrite("spi_decoded_mosi",&PyOptions::spi_decoded_mosi)
        .def_readwrite("spi_decoded_miso",&PyOptions::spi_decoded_miso)
        .def_readwrite("workqueue_intervals_spi",&PyOptions::workqueue_intervals_spi)
        .def_readwrite("timestamp_spi",&PyOptions::timestamp_spi)
        .def_readwrite("timestamp_end_spi",&PyOptions::timestamp_end_spi)
        .def_readwrite("sync_digital",&PyOptions::sync_digital)
        ;

    py::enum_<TSType>(handle, "TSType")
        .value("TSNone", TSType::TSNone)
        .value("TSAbsolute", TSType::TSAbsolute)
        .value("TSRelative", TSType::TSRelative)
        .value("TSDelta", TSType::TSDelta)
        .value("TSStamp", TSType::TSStamp)
        .value("TSStampDelta", TSType::TSStampDelta)
        .value("TSNumTypes", TSType::TSNumTypes)
        .export_values();
}