project('orbuculum', ['c', 'cpp'], default_options: ['cpp_std=c++20'])

orbuculum = subproject('orbuculum')
liborb = orbuculum.get_variable('liborb')
git_version_info_h = orbuculum.get_variable('git_version_info_h')

perfetto = subproject('perfetto')
libperfetto_protos = perfetto.get_variable('libperfetto_protos')

executable('orbetto',
    sources: [
        'orbetto.cpp',
        'loadelf.c',
        git_version_info_h,
    ],
    include_directories: include_directories(['subprojects/orbuculum/Inc', 'subprojects/perfetto', '.']),
    dependencies: [dependency('protobuf'), dependency('libelf'), dependency('libdwarf')],
    link_with: [liborb, libperfetto_protos],
    install: true,
)
