#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "orbetto.cpp"

namespace py = pybind11;

PYBIND11_MODULE(orbethon,handle){
    handle.doc()="Python rapper for orbetto tool.";
    handle.def("orbethon",&main_pywrapper);

    py::class_<Options>(handle,"Options_Struct")
        /* Default class init for python */
        .def(py::init())
        /* Config information */
        //.def_readwrite("useTPIU",&Options::useTPIU)
        //.def_readwrite("tpiuChannel",&Options::tpiuChannel)
        //.def_readwrite("forceITMSync",&Options::forceITMSync)
        .def_readwrite("cps",&Options::cps)
        .def_readwrite("tsType",&Options::tsType)
        //.def_readwrite("tsLineFormat",&Options::tsLineFormat)
        //.def_readwrite("tsTrigger",&Options::tsTrigger)
        /* Sink information */
        // careful this is different from c++ implementation and has to be converted as pybind has no char*[]
        //.def_readwrite("presFormat",&Options::presFormat)
        /* Source information */
        //.def_readwrite("port",&Options::port)
        //.def_readwrite("server",&Options::server)
        .def_readwrite("file",&Options::std_file)
        .def_readwrite("endTerminate",&Options::endTerminate)
        //.def_readwrite("outputDebugFile",&Options::outputDebugFile)
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