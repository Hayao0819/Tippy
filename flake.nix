{
  description = "ComicFuz-Down-Plus development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # protoc and the protobuf runtime come from the same nixpkgs, so the
        # generated fuz_pb2.py always matches the installed google.protobuf.
        python = pkgs.python3.withPackages (ps: with ps; [
          protobuf
          cryptography
          pillow
          requests
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.protobuf # protoc
            pkgs.uv
          ];

          shellHook = ''
            echo "ComicFuz-Down-Plus — $(python --version), $(protoc --version)"
          '';
        };
      });
}
