#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "orbetto.cpp"

namespace py = pybind11;

PYBIND11_MODULE(orbethon,handle){
    handle.doc()="Python rapper for orbetto tool.";
    handle.def("orbethon",&main_pywrapper);
}