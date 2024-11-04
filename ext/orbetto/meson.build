project('orbetto', ['c', 'cpp'], default_options: ['cpp_std=c++20'])

# Clone the perfetto git repository
subproject('perfetto')

# find the all relevant protobuf source files
proto_sources_output = run_command('subprojects/proto.sh', check: true)
proto_sources = proto_sources_output.stdout().strip().split('\n')

# Configure the protoc compiler
cpp_gen = generator(find_program('protoc'), output: ['@BASENAME@.pb.cc', '@BASENAME@.pb.h'],
                    arguments: ['--proto_path=@CURRENT_SOURCE_DIR@/subprojects/perfetto/', '--cpp_out=@BUILD_DIR@', '@INPUT@'])
# Generate the protobuf source and header files
perfbuf_sources = cpp_gen.process(proto_sources, preserve_path_from: meson.current_source_dir() + '/subprojects/perfetto/')
# Compile and link the protobuf source files
perfbuf_lib = static_library('perfbuf', sources: perfbuf_sources, dependencies: [dependency('protobuf')])

# Specify the include directory for Roaring Bitmap
cmake = import('cmake')
rm = cmake.subproject('croaring')
# Fetch the dependency object
message('CMake targets:\n - ' + '\n - '.join(rm.target_list()))
rm_dep1 = rm.dependency('roaring-headers-cpp')
rm_dep2 = rm.dependency('roaring-headers')
rm_dep = rm.dependency('roaring')
rm_inc = rm.get_variable('roaring_headers_cpp_inc') + rm.get_variable('roaring_headers_inc')


# Clone the orbuculum git repository
orbuculum = subproject('orbuculum')
liborb = orbuculum.get_variable('liborb')
orbinc = orbuculum.get_variable('incdirs')
git_version_info_h = orbuculum.get_variable('git_version_info_h')

# Compile and link everything together
executable('orbetto',
    sources: ['src/orbetto.cpp', 'src/device.cpp', git_version_info_h],
    include_directories: ['src'] + perfbuf_lib.private_dir_include() + orbinc + rm_inc,
    dependencies: [dependency('protobuf')] + orbuculum.get_variable('dependencies') + [rm_dep] + [rm_dep1] + [rm_dep2],
    link_with: [liborb, perfbuf_lib],
    install: true,
)
