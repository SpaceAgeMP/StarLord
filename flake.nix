{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";

    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, flake-utils, pyproject-nix, uv2nix, pyproject-build-systems, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;

        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
        python = pkgs.python312;
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            inherit python;
          }).overrideScope
            (
              nixpkgs.lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                overlay
              ]
            );

        package = mkApplication {
          venv = pythonSet.mkVirtualEnv "starlord" workspace.deps.default;
          package = pythonSet.starlord;
        };
      in
      {
        packages = {
          default = package;
          starlord = package;
        };
      });
}
