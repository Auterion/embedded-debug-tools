# go get a coffee while this downloads
git clone https://github.com/google/perfetto.git perfetto_src

# remote existing files
rm -rf protos

# Regenerate all trace packet protobuf definitions
protoc --proto_path=perfetto_src/ --include_imports --descriptor_set_out=/dev/stdout perfetto_src/protos/perfetto/trace/trace.proto | \
	protoc --decode=google.protobuf.FileDescriptorSet google/protobuf/descriptor.proto | \
	rg "^  name: \"(.*?)\"" -r "\$1" | \
	xargs -I {} protoc --proto_path=perfetto_src/ --cpp_out=. {}

# find all the source files to update the meson.build list
find . -name "*.cc"
