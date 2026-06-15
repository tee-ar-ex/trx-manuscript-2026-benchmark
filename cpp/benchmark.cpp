#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <chrono>
#include <filesystem>
#include <cstdlib>
#include <map>
#include "utils.hpp"

namespace fs = std::filesystem;

const std::vector<std::string> FILENAMES = {
    "f16_ui32_w_metadata.trx", "f16_ui32_wo_metadata.trx",
    "f16_ui64_w_metadata.trx", "f16_ui64_wo_metadata.trx",
    "f32_ui64_w_metadata.trx", "f32_ui64_wo_metadata.trx",
    "f64_ui32_w_metadata.trx", "f64_ui32_wo_metadata.trx",
    "f32_ui32_w_metadata.trx", "f32_ui32_wo_metadata.trx",
    "f64_ui64_w_metadata.trx", "f64_ui64_wo_metadata.trx",
    "f32_w_metadata.trk", "f32_wo_metadata.trk", "f32.tck",
    "f32_ui32_wo_metadata.vtk", "f32_ui64_wo_metadata.vtk",
    "f64_ui32_wo_metadata.vtk", "f64_ui64_wo_metadata.vtk",
    "f32_ui64_w_metadata.vtk", "f64_ui64_w_metadata.vtk"
};

int main() {
    // 1. Get data directory from environment variable
    const char* env_dir = std::getenv("TRX_BENCHMARK_DATA_DIR");
    std::string data_dir = env_dir ? env_dir : "";
    if (data_dir.empty()) {
        std::cerr << "[ERROR] TRX_BENCHMARK_DATA_DIR environment variable is not set." << std::endl;
        return 1;
    }
    
    std::cout << "Data directory: " << data_dir << std::endl;
    
    std::map<std::string, std::vector<double>> loading_results;
    std::map<std::string, std::vector<double>> saving_results;
    
    // Create temp directory for saving
    std::string tmp_dir = "tmp_benchmark_saving";
    fs::create_directories(tmp_dir);
    
    for (const auto& filename : FILENAMES) {
        fs::path file_path = fs::path(data_dir) / filename;
        if (!fs::exists(file_path)) {
            std::cout << "[SKIP] " << filename << " not found." << std::endl;
            continue;
        }
        
        std::string ext = file_path.extension().string();
        std::cout << "Benchmarking Loading for " << filename << " (11 iterations)..." << std::endl;
        
        std::vector<double> load_times;
        bool load_success = true;
        
        for (int i = 0; i < 11; ++i) {
            evict_from_cache(file_path.string());
            release_memory();
            
            auto t0 = std::chrono::high_resolution_clock::now();
            Tractogram tr;
            bool success = false;
            
            if (ext == ".trx") {
                success = load_trx(file_path.string(), tr);
            } else if (ext == ".trk") {
                success = load_trk(file_path.string(), tr);
            } else if (ext == ".tck") {
                success = load_tck(file_path.string(), tr);
            } else if (ext == ".vtk") {
                success = load_vtk(file_path.string(), tr);
            }
            
            auto t1 = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double> diff = t1 - t0;
            double duration = diff.count();
            
            if (!success) {
                std::cerr << "    " << i << " - [ERROR] Loading failed" << std::endl;
                load_success = false;
                break;
            }
            
            // Validate sizes
            size_t streamline_count = tr.offsets.size() - 1;
            size_t point_count = tr.pts.size() / 3;
            if (streamline_count != 5979093 || point_count != 201521017) {
                std::cerr << "    " << i << " - [FAIL] " << filename << " - Wrong size detected! streamlines=" 
                          << streamline_count << ", points=" << point_count << std::endl;
                load_success = false;
                break;
            }
            
            if (i == 0) {
                std::cout << "    [COLD RUN] " << duration << "s (Initialization overhead)" << std::endl;
            } else {
                load_times.push_back(duration);
                std::cout << "    " << (i - 1) << " - " << duration << "s" << std::endl;
            }
            
            release_memory();
        }
        
        if (load_success && !load_times.empty()) {
            loading_results[filename] = load_times;
            double sum = 0;
            for (double t : load_times) sum += t;
            double avg = sum / load_times.size();
            std::cout << "Summary for " << filename << ": " << avg << " seconds.\n" << std::endl;
        }
        
        // Benchmarking Saving (for all formats)
        if (load_success) {
            std::cout << "Benchmarking Saving for " << filename << " (11 iterations)..." << std::endl;
            std::vector<double> save_times;
            bool save_success = true;
            
            // Load tractogram once into memory to isolate save time
            Tractogram tr;
            if (ext == ".trx") load_trx(file_path.string(), tr);
            else if (ext == ".trk") load_trk(file_path.string(), tr);
            else if (ext == ".tck") load_tck(file_path.string(), tr);
            else if (ext == ".vtk") load_vtk(file_path.string(), tr);
            
            for (int i = 0; i < 11; ++i) {
                release_memory();
                fs::path save_path = fs::path(tmp_dir) / ("tmp_save_" + std::to_string(i) + ext);
                
                auto t0 = std::chrono::high_resolution_clock::now();
                bool success = false;
                if (ext == ".trx") {
                    success = save_trx(tr, save_path.string());
                } else if (ext == ".trk") {
                    success = save_trk(tr, save_path.string(), filename);
                } else if (ext == ".tck") {
                    success = save_tck(tr, save_path.string());
                } else if (ext == ".vtk") {
                    success = save_vtk(tr, save_path.string());
                }
                auto t1 = std::chrono::high_resolution_clock::now();
                
                std::chrono::duration<double> diff = t1 - t0;
                double duration = diff.count();
                
                if (fs::exists(save_path)) {
                    fs::remove(save_path);
                }
                
                if (!success) {
                    std::cerr << "    " << i << " - [ERROR] Saving failed" << std::endl;
                    save_success = false;
                    break;
                }
                
                if (i == 0) {
                    std::cout << "    [COLD RUN] " << duration << "s (Initialization overhead)" << std::endl;
                } else {
                    save_times.push_back(duration);
                    std::cout << "    " << (i - 1) << " - " << duration << "s" << std::endl;
                }
            }
            
            if (save_success && !save_times.empty()) {
                saving_results[filename] = save_times;
                double sum = 0;
                for (double t : save_times) sum += t;
                double avg = sum / save_times.size();
                std::cout << "Summary for " << filename << ": " << avg << " seconds.\n" << std::endl;
            }
        }
    }
    
    // Cleanup tmp_dir
    if (fs::exists(tmp_dir)) {
        fs::remove_all(tmp_dir);
    }
    
    // Write results to results/cpp_results.json
    fs::create_directories("results");
    std::ofstream out("results/cpp_results.json");
    if (out.is_open()) {
        out << "{\n";
        out << "  \"language\": \"cpp\",\n";
        out << "  \"data_directory\": \"" << data_dir << "\",\n";
        out << "  \"results\": {\n";
        
        // Write loading
        out << "    \"loading\": {\n";
        size_t l_idx = 0;
        for (const auto& [name, times] : loading_results) {
            out << "      \"" << name << "\": [";
            for (size_t i = 0; i < times.size(); ++i) {
                out << times[i];
                if (i + 1 < times.size()) out << ", ";
            }
            out << "]";
            if (++l_idx < loading_results.size()) out << ",";
            out << "\n";
        }
        out << "    },\n";
        
        // Write saving
        out << "    \"saving\": {\n";
        size_t s_idx = 0;
        for (const auto& [name, times] : saving_results) {
            out << "      \"" << name << "\": [";
            for (size_t i = 0; i < times.size(); ++i) {
                out << times[i];
                if (i + 1 < times.size()) out << ", ";
            }
            out << "]";
            if (++s_idx < saving_results.size()) out << ",";
            out << "\n";
        }
        out << "    }\n";
        
        out << "  }\n";
        out << "}\n";
        out.close();
        std::cout << "Results saved to results/cpp_results.json" << std::endl;
    } else {
        std::cerr << "[ERROR] Failed to open results/cpp_results.json for writing." << std::endl;
    }
    
    return 0;
}
