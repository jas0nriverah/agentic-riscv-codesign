; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x39 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv64 32))))
(let ((?x41 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x54 (bvshl (bvadd independent_opaque_0 (_ bv16 32)) ?x41)))
(and (distinct ?x54 ?x39) true)))))
(check-sat)
