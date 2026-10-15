; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x41 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x24 (bvshl (bvadd independent_opaque_0 independent_opaque_1) ?x41)))
(and (distinct ?x24 ?x15) true)))))
(check-sat)
