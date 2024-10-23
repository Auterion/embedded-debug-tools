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

# Clone the orbuculum git repository
orbuculum = subproject('orbuculum')
liborb = orbuculum.get_variable('liborb')
orbinc = orbuculum.get_variable('incdirs')
git_version_info_h = orbuculum.get_variable('git_version_info_h')

# Specify the include directory for Roaring Bitmap
cmake = import('cmake')
croaring = cmake.subproject('croaring')
message('CMake targets:\n - ' + '\n - '.join(croaring.target_list()))
# Fetch the dependency object
cm_lib1 = croaring.dependency('roaring-headers')
cm_lib2 = croaring.dependency('roaring-headers-cpp')
inc = croaring.get_variable('roaring_inc')

# Compile and link everything together
executable('orbetto',
    sources: ['src/orbetto.cpp', 'src/device.cpp', git_version_info_h],
    include_directories: ['src'] + perfbuf_lib.private_dir_include() + orbinc + inc,
    dependencies: [dependency('protobuf')] + orbuculum.get_variable('dependencies') + [cm_lib1] + [cm_lib2],
    link_with: [liborb, perfbuf_lib],
    install: true,
)
