{
  description = "A Node devshell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
      in
      {
        devShells.default =
          with pkgs;
          mkShell {
            buildInputs = [
              nodejs
              python3
              pkg-config
            ];
            shellHook = ''
              if ! cmp -s backend/requirements.txt .venv/requirements.txt; then
                python3 -m venv .venv
                .venv/bin/pip install -q -r backend/requirements.txt
                cp backend/requirements.txt .venv/requirements.txt
              fi
              source .venv/bin/activate
            '';
          };
      }
    );
}
