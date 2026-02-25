FROM confluentinc/cp-kafka:7.6.1
WORKDIR /work
COPY init-topics.sh /work/init-topics.sh
RUN chmod +x /work/init-topics.sh
CMD ["/work/init-topics.sh"]
