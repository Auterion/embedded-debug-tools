#!/usr/bin/env bash
# Regenerate all trace packet protobuf definitions
protoc --proto_path=subprojects/perfetto --include_imports --descriptor_set_out=/dev/stdout subprojects/perfetto/protos/perfetto/trace/trace.proto | \
	protoc --decode=google.protobuf.FileDescriptorSet google/protobuf/descriptor.proto | \
	sed -rn "s#^  name: \"(.*)\"#subprojects/perfetto/\1#p"
