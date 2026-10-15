; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x9 (bvshl independent_opaque_0 (bvand (_ bv4 32) (_ bv31 32)))))
(let ((?x35 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvadd ?x9 independent_opaque_1))))
(let ((?x24 (bvadd (bvsub ?x9 independent_opaque_0) independent_opaque_1)))
(and (distinct ?x24 ?x35) true)))))
(check-sat)
