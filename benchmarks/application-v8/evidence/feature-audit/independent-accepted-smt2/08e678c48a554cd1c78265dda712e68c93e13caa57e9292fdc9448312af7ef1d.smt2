; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x16 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967168 32))))
(let ((?x41 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x557 (bvshl (bvadd independent_opaque_0 (_ bv4294967264 32)) ?x41)))
(and (distinct ?x557 ?x16) true)))))
(check-sat)
