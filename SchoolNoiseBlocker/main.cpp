// Simple program: appends two hosts entries and flushes DNS
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

const char* HOSTS_PATH = "C:\\Windows\\System32\\drivers\\etc\\hosts";

int main(){
    std::vector<std::string> lines = {"127.0.0.1 www.bilibili.com", "127.0.0.1 www.douyin.com"};
    std::string content;
    {
        std::ifstream in(HOSTS_PATH);
        if(!in){ std::cerr << "Cannot open hosts file (run as admin)\n"; return 1; }
        std::ostringstream ss; ss << in.rdbuf(); content = ss.str();
    }

    bool changed = false;
    for(const auto &ln : lines){
        if(content.find(ln) == std::string::npos){
            std::ofstream out(HOSTS_PATH, std::ios::app);
            if(!out){ std::cerr << "Cannot write to hosts file (permission)\n"; return 2; }
            out << ln << "\r\n";
            changed = true;
        }
    }

    if(changed){
        // flush DNS cache
        system("ipconfig /flushdns >nul 2>&1");
    }
    return 0;
}
