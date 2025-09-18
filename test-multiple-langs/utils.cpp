 
#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <memory>
#include <unordered_map>
#include <functional>
#include <thread>
#include <mutex>
#include <future>
#include "user.h"
#include "database.h"

namespace utils {

template<typename T>
T findMax(const std::vector<T>& vec) {
    if (vec.empty()) {
        throw std::invalid_argument("Vector cannot be empty");
    }
    return *std::max_element(vec.begin(), vec.end());
}

template<>
std::string findMax<std::string>(const std::vector<std::string>& vec) {
    if (vec.empty()) {
        throw std::invalid_argument("Vector cannot be empty");
    }
    return *std::max_element(vec.begin(), vec.end(),
        [](const std::string& a, const std::string& b) {
            return a.length() < b.length();
        });
}

int add(int a, int b) {
    return a + b;
}

double add(double a, double b) {
    return a + b;
}

std::string add(const std::string& a, const std::string& b) {
    return a + b;
}

auto createMultiplier(int factor) {
    return [factor](int value) {
        return value * factor;
    };
}

class StringProcessor {
private:
    std::string delimiter_;
    mutable std::mutex mutex_;

public:
    explicit StringProcessor(const std::string& delimiter)
        : delimiter_(delimiter) {}

    std::vector<std::string> split(const std::string& input) const {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<std::string> result;
        size_t start = 0;
        size_t end = input.find(delimiter_);

        while (end != std::string::npos) {
            result.push_back(input.substr(start, end - start));
            start = end + delimiter_.length();
            end = input.find(delimiter_, start);
        }
        result.push_back(input.substr(start));
        return result;
    }

    std::string join(const std::vector<std::string>& parts) const {
        if (parts.empty()) return "";

        std::string result = parts[0];
        for (size_t i = 1; i < parts.size(); ++i) {
            result += delimiter_ + parts[i];
        }
        return result;
    }

    static std::unique_ptr<StringProcessor> create(const std::string& delimiter) {
        return std::make_unique<StringProcessor>(delimiter);
    }
};

class AdvancedStringProcessor : public StringProcessor {
private:
    bool caseSensitive_;

public:
    AdvancedStringProcessor(const std::string& delimiter, bool caseSensitive = true)
        : StringProcessor(delimiter), caseSensitive_(caseSensitive) {}

    std::string normalize(const std::string& input) const {
        if (!caseSensitive_) {
            std::string result = input;
            std::transform(result.begin(), result.end(), result.begin(), ::tolower);
            return result;
        }
        return input;
    }

    bool contains(const std::string& haystack, const std::string& needle) const {
        std::string normalizedHaystack = normalize(haystack);
        std::string normalizedNeedle = normalize(needle);
        return normalizedHaystack.find(normalizedNeedle) != std::string::npos;
    }
};

using ProcessCallback = std::function<void(const std::string&)>;

void processFiles(const std::vector<std::string>& files, ProcessCallback callback) {
    for (const auto& file : files) {
        callback(file);
    }
}

std::future<int> calculateAsync(int n) {
    return std::async(std::launch::async, [n]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        return n * n;
    });
}

template<typename K, typename V>
class Cache {
private:
    std::unordered_map<K, V> data_;
    mutable std::mutex mutex_;
    size_t maxSize_;

public:
    explicit Cache(size_t maxSize = 100) : maxSize_(maxSize) {}

    void put(const K& key, const V& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (data_.size() >= maxSize_) {
            data_.clear();  
        }
        data_[key] = value;
    }

    bool get(const K& key, V& value) const {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = data_.find(key);
        if (it != data_.end()) {
            value = it->second;
            return true;
        }
        return false;
    }

    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        data_.clear();
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return data_.size();
    }
};

}  

void printBanner(const std::string& message) {
    std::cout << "=== " << message << " ===" << std::endl;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main() {
    printBanner("C++ Function Scanner Test");

    std::vector<int> numbers = {1, 5, 3, 9, 2};
    int maxNum = utils::findMax(numbers);
    std::cout << "Max number: " << maxNum << std::endl;

    auto processor = utils::StringProcessor::create(",");
    std::vector<std::string> parts = processor->split("a,b,c,d");
    std::string joined = processor->join(parts);
    std::cout << "Joined: " << joined << std::endl;

    auto future = utils::calculateAsync(5);
    int result = future.get();
    std::cout << "Async result: " << result << std::endl;

    utils::Cache<std::string, int> cache;
    cache.put("key1", 42);

    int value;
    if (cache.get("key1", value)) {
        std::cout << "Cache value: " << value << std::endl;
    }

    return 0;
}