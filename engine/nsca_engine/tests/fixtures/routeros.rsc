# MikroTik RouterOS export fixture (hand-written, TRD-00 §8 fixture class)
/ip service
set telnet disabled=yes port=23
set www disabled=no port=80
set ssh disabled=no port=22
/system ntp client
set enabled=yes primary-ntp=10.0.0.10
/interface ethernet
set [ find default-name=ether1 ] name=ether1-wan
