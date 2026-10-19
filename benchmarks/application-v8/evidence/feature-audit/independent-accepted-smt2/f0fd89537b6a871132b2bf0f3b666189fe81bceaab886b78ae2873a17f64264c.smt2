; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x622 (bvadd independent_opaque_1 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32)))))))
(let ((?x16 (bvadd independent_opaque_0 ?x622)))
(let ((?x61 (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32)))))
(let ((?x39 (bvsub independent_opaque_0 (bvsub ?x61 independent_opaque_1))))
(and (distinct ?x39 ?x16) true))))))
(check-sat)
