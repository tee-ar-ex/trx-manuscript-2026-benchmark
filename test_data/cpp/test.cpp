#include "utils.hpp"
using namespace trx::legacy;
#include <iostream>
#include <string>
#include <filesystem>

namespace fs = std::filesystem;

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: test_cpp <input_file> <output_file> [--ref <nifti>]" << std::endl;
        return 1;
    }
    std::string input_file = argv[1];
    std::string output_file = argv[2];
    std::string ref_nifti = "";
    if (argc >= 5 && std::string(argv[3]) == "--ref") {
        ref_nifti = argv[4];
    }
    std::string ext = fs::path(input_file).extension().string();
    std::string out_ext = fs::path(output_file).extension().string();

    Tractogram tr;
    bool loaded = false;

    if (ext == ".trx") {
        loaded = load_trx(input_file, tr);
    } else if (ext == ".trk") {
        loaded = load_trk(input_file, tr);
    } else if (ext == ".tck") {
        loaded = load_tck(input_file, tr);
    } else if (ext == ".vtk") {
        loaded = load_vtk(input_file, tr);
    } else {
        std::cerr << "Unsupported input format: " << ext << std::endl;
        return 1;
    }

    if (!loaded) {
        std::cerr << "Failed to load: " << input_file << std::endl;
        return 1;
    }

    bool saved = false;
    if (out_ext == ".trx") {
        saved = save_trx(tr, output_file);
    } else if (out_ext == ".trk") {
        saved = save_trk(tr, output_file, fs::path(input_file).filename().string(), ref_nifti);
    } else if (out_ext == ".tck") {
        saved = save_tck(tr, output_file);
    } else if (out_ext == ".vtk") {
        saved = save_vtk(tr, output_file);
    } else {
        std::cerr << "Unsupported output format: " << out_ext << std::endl;
        return 1;
    }

    if (!saved) {
        std::cerr << "Failed to save: " << output_file << std::endl;
        return 1;
    }

    return 0;
}
