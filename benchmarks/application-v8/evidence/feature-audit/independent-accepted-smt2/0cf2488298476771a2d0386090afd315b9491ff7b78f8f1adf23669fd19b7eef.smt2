; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x613 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967184 32))))
(let ((?x41 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x49 (bvshl (bvadd independent_opaque_0 (_ bv4294967268 32)) ?x41)))
(and (distinct ?x49 ?x613) true)))))
(check-sat)
